import Cocoa

let outputPath = "/tmp/mail_helper_output.txt"

func writeOutput(_ text: String) {
    try? text.write(toFile: outputPath, atomically: true, encoding: .utf8)
}

/// Delete the mail cache so the next dashboard generation fetches fresh data
func invalidateMailCache() {
    let home = FileManager.default.homeDirectoryForCurrentUser
    let cache = home
        .appendingPathComponent("Code")
        .appendingPathComponent(".mail_cache.json")
    try? FileManager.default.removeItem(at: cache)
}

/// Run an AppleScript and return its result
func runAppleScript(_ source: String) -> String? {
    let script = NSAppleScript(source: source)
    var error: NSDictionary?
    let result = script?.executeAndReturnError(&error)
    if let err = error {
        let msg = err[NSAppleScript.errorMessage] as? String ?? "Unknown error"
        return "ERROR:\(msg)"
    }
    return result?.stringValue
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var handledURL = false

    func applicationWillFinishLaunching(_ notification: Notification) {
        NSAppleEventManager.shared().setEventHandler(
            self,
            andSelector: #selector(handleURL(_:withReply:)),
            forEventClass: AEEventClass(kInternetEventClass),
            andEventID: AEEventID(kAEGetURL)
        )
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            if !self.handledURL {
                writeOutput("OK:MailHelper ready")
                NSApp.terminate(nil)
            }
        }
    }

    @objc func handleURL(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        handledURL = true
        guard let urlString = event.paramDescriptor(forKeyword: AEKeyword(keyDirectObject))?.stringValue,
              let url = URL(string: urlString) else {
            writeOutput("ERROR:Invalid URL")
            NSApp.terminate(nil)
            return
        }

        let command = url.host ?? ""
        let params = URLComponents(url: url, resolvingAgainstBaseURL: false)?
            .queryItems?.reduce(into: [String: String]()) { dict, item in
                dict[item.name] = item.value
            } ?? [:]


        switch command {
        case "delete":
            guard let messageId = params["id"], !messageId.isEmpty else {
                writeOutput("ERROR:Missing message id")
                NSApp.terminate(nil)
                return
            }
            handleDelete(messageId: messageId)

        case "move":
            guard let messageId = params["id"], !messageId.isEmpty else {
                writeOutput("ERROR:Missing message id")
                NSApp.terminate(nil)
                return
            }
            guard let folder = params["folder"], !folder.isEmpty else {
                writeOutput("ERROR:Missing folder")
                NSApp.terminate(nil)
                return
            }
            handleMove(messageId: messageId, folder: folder)

        case "open":
            guard let messageId = params["id"], !messageId.isEmpty else {
                writeOutput("ERROR:Missing message id")
                NSApp.terminate(nil)
                return
            }
            handleOpen(messageId: messageId)

        default:
            writeOutput("ERROR:Unknown command: \(command)")
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            NSApp.terminate(nil)
        }
    }

    func handleDelete(messageId: String) {
        let script: String

        // Helper AppleScript snippet: given targetMsg, move to account trash or delete
        let doDelete = """
                    set msgAcct to account of (mailbox of targetMsg)
                    set trashBox to missing value
                    repeat with mb in mailboxes of msgAcct
                        if name of mb is "Trash" or name of mb is "Deleted Messages" then
                            set trashBox to mb
                            exit repeat
                        end if
                    end repeat
                    if trashBox is not missing value then
                        move targetMsg to trashBox
                    else
                        delete targetMsg
                    end if
                    return "OK:Deleted"
        """

        if messageId.hasPrefix("mailid:") {
            let internalId = String(messageId.dropFirst(7))
            script = """
            tell application "Mail"
                -- Search only INBOX of each account to avoid finding deleted copies
                set targetMsg to missing value
                repeat with acct in accounts
                    try
                        set msgList to messages of inbox of acct
                        repeat with msg in msgList
                            if (id of msg as string) is "\(internalId)" then
                                set targetMsg to msg
                                exit repeat
                            end if
                        end repeat
                    end try
                    if targetMsg is not missing value then exit repeat
                end repeat
                if targetMsg is not missing value then
                    \(doDelete)
                else
                    return "ERROR:Message not found"
                end if
            end tell
            """
        } else {
            // RFC message-id — search only INBOX of each account
            script = """
            tell application "Mail"
                set targetMsg to missing value
                -- Check top-level inbox first
                try
                    set hits to (messages of inbox whose message id is "\(messageId)")
                    if (count of hits) > 0 then set targetMsg to item 1 of hits
                end try
                -- Then each account's inbox
                if targetMsg is missing value then
                    repeat with acct in accounts
                        try
                            set hits to (messages of inbox of acct whose message id is "\(messageId)")
                            if (count of hits) > 0 then
                                set targetMsg to item 1 of hits
                                exit repeat
                            end if
                        end try
                    end repeat
                end if
                if targetMsg is not missing value then
                    \(doDelete)
                else
                    return "ERROR:Message not found"
                end if
            end tell
            """
        }

        if let result = runAppleScript(script) {
            if result.hasPrefix("OK:") { invalidateMailCache() }
            writeOutput(result)
        } else {
            writeOutput("ERROR:AppleScript execution failed")
        }
    }

    func handleMove(messageId: String, folder: String) {
        let script: String

        if messageId.hasPrefix("mailid:") {
            let internalId = String(messageId.dropFirst(7))
            script = """
            tell application "Mail"
                -- Find message by internal id (must loop — no whose filter for id)
                set targetMsg to missing value
                set msgList to messages of inbox
                repeat with msg in msgList
                    try
                        if (id of msg as string) is "\(internalId)" then
                            set targetMsg to msg
                            exit repeat
                        end if
                    end try
                end repeat
                if targetMsg is missing value then
                    return "ERROR:Message not found"
                end if
                -- Search all accounts for the destination folder (cross-account moves allowed)
                set destBox to missing value
                repeat with acct in accounts
                    repeat with mb in mailboxes of acct
                        if name of mb is "\(folder)" then
                            set destBox to mb
                            exit repeat
                        end if
                    end repeat
                    if destBox is not missing value then exit repeat
                end repeat
                if destBox is missing value then return "ERROR:Folder not found: \(folder)"
                move targetMsg to destBox
                return "OK:Moved"
            end tell
            """
        } else {
            // RFC message-id: use whose for fast message lookup, iterate for folder
            script = """
            tell application "Mail"
                -- Fast message lookup via whose
                set targetMsg to missing value
                try
                    set hits to (messages of inbox whose message id is "\(messageId)")
                    if (count of hits) > 0 then set targetMsg to item 1 of hits
                end try
                if targetMsg is missing value then
                    repeat with acct in accounts
                        try
                            set hits to (messages of inbox of acct whose message id is "\(messageId)")
                            if (count of hits) > 0 then
                                set targetMsg to item 1 of hits
                                exit repeat
                            end if
                        end try
                    end repeat
                end if
                if targetMsg is missing value then return "ERROR:Message not found"

                -- Search all accounts for the destination folder (cross-account moves allowed)
                set destBox to missing value
                repeat with acct in accounts
                    repeat with mb in mailboxes of acct
                        if name of mb is "\(folder)" then
                            set destBox to mb
                            exit repeat
                        end if
                    end repeat
                    if destBox is not missing value then exit repeat
                end repeat
                if destBox is missing value then return "ERROR:Folder not found: \(folder)"

                move targetMsg to destBox
                return "OK:Moved to \(folder)"
            end tell
            """
        }

        if let result = runAppleScript(script) {
            if result.hasPrefix("OK:") { invalidateMailCache() }
            writeOutput(result)
        } else {
            writeOutput("ERROR:AppleScript execution failed")
        }
    }

    func handleOpen(messageId: String) {
        let script: String

        if messageId.hasPrefix("mailid:") {
            let internalId = String(messageId.dropFirst(7))
            script = """
            tell application "Mail"
                set targetMsg to missing value
                set msgList to messages of inbox
                repeat with msg in msgList
                    try
                        if (id of msg as string) is "\(internalId)" then
                            set targetMsg to msg
                            exit repeat
                        end if
                    end try
                end repeat
                if targetMsg is not missing value then
                    open targetMsg
                    activate
                    return "OK:Message opened"
                else
                    return "ERROR:Message not found in inbox"
                end if
            end tell
            """
        } else {
            // Use whose for fast lookup
            script = """
            tell application "Mail"
                set targetMsg to missing value
                try
                    set hits to (messages of inbox whose message id is "\(messageId)")
                    if (count of hits) > 0 then set targetMsg to item 1 of hits
                end try
                if targetMsg is missing value then
                    repeat with acct in accounts
                        try
                            set hits to (messages of inbox of acct whose message id is "\(messageId)")
                            if (count of hits) > 0 then
                                set targetMsg to item 1 of hits
                                exit repeat
                            end if
                        end try
                    end repeat
                end if
                if targetMsg is not missing value then
                    open targetMsg
                    activate
                    return "OK:Message opened"
                else
                    return "ERROR:Message not found"
                end if
            end tell
            """
        }

        if let result = runAppleScript(script) {
            writeOutput(result)
        } else {
            writeOutput("ERROR:AppleScript execution failed")
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
