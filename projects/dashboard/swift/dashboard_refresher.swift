import Cocoa

// DashboardRefresher
// Handles the refreshdashboard:// URL scheme.
// Also ensures the HTTP server (dashboard_server.py) is running at all times.

let logFile = "/tmp/dashboard-refresh.log"

func log(_ message: String) {
    let timestamp = ISO8601DateFormatter().string(from: Date())
    let line = "[\(timestamp)] \(message)\n"
    if let handle = FileHandle(forWritingAtPath: logFile) {
        handle.seekToEndOfFile()
        handle.write(line.data(using: .utf8)!)
        handle.closeFile()
    } else {
        FileManager.default.createFile(atPath: logFile, contents: line.data(using: .utf8))
    }
}

// Check if something is listening on port 8080, and if not, start dashboard_server.py
func ensureServerRunning(projectDir: URL) {
    let check = Process()
    check.executableURL = URL(fileURLWithPath: "/bin/bash")
    check.arguments = ["-c", "lsof -ti :8080 | head -1"]
    let pipe = Pipe()
    check.standardOutput = pipe
    check.standardError = Pipe()
    try? check.run()
    check.waitUntilExit()
    let output = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""

    if output.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        // Nothing on port 8080 — start the server
        let serverScript = projectDir.appendingPathComponent("dashboard_server.py").path
        // Also check home directory fallback
        let homeServer = "/Users/\(NSUserName())/dashboard_server.py"
        let scriptToUse = FileManager.default.fileExists(atPath: serverScript) ? serverScript : homeServer

        log("Starting HTTP server: \(scriptToUse)")
        let server = Process()
        server.executableURL = URL(fileURLWithPath: "/bin/bash")
        server.arguments = ["-l", "-c", "/usr/bin/python3 '\(scriptToUse)' >> /tmp/dashboard-server.log 2>&1 &"]
        server.standardOutput = Pipe()
        server.standardError = Pipe()
        try? server.run()
        // Don't wait — let it run in background
        log("HTTP server started.")
    } else {
        log("HTTP server already running (pid \(output.trimmingCharacters(in: .whitespacesAndNewlines))).")
    }
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
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            if !self.handledURL {
                log("Launched without URL — running dashboard refresh directly")
                self.runDashboard()
            }
        }
    }

    @objc func handleURL(_ event: NSAppleEventDescriptor, withReply reply: NSAppleEventDescriptor) {
        handledURL = true
        let urlString = event.paramDescriptor(forKeyword: AEKeyword(keyDirectObject))?.stringValue ?? "(none)"
        log("Received URL: \(urlString)")
        runDashboard()
    }

    func runDashboard() {
        let appBundlePath = Bundle.main.bundlePath
        let appsDir = URL(fileURLWithPath: appBundlePath).deletingLastPathComponent()
        let projectDir = appsDir.deletingLastPathComponent()
        let projectDirPath = projectDir.path
        let dashboardScript = projectDir.appendingPathComponent("dashboard.py").path

        // Ensure HTTP server is running before we regenerate
        ensureServerRunning(projectDir: projectDir)

        log("Project dir: \(projectDirPath)")
        log("Running: /bin/bash -l -c 'cd \(projectDirPath) && /usr/bin/python3 \(dashboardScript)'")

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [
            "-l", "-c",
            "cd '\(projectDirPath)' && /usr/bin/python3 '\(dashboardScript)'"
        ]
        process.currentDirectoryURL = projectDir

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        var outputData = Data()
        let readingDone = DispatchSemaphore(value: 0)
        DispatchQueue.global().async {
            outputData = pipe.fileHandleForReading.readDataToEndOfFile()
            readingDone.signal()
        }

        do {
            try process.run()
            process.waitUntilExit()
            pipe.fileHandleForReading.closeFile()
            readingDone.wait()

            let output = String(data: outputData, encoding: .utf8) ?? ""

            if process.terminationStatus == 0 {
                log("Dashboard refreshed successfully.")
                if !output.isEmpty {
                    log("Output: \(output.prefix(500))")
                }
            } else {
                log("ERROR: dashboard.py exited with code \(process.terminationStatus)")
                if !output.isEmpty {
                    log("Output: \(output.prefix(1000))")
                }
            }
        } catch {
            log("ERROR: Failed to launch dashboard.py — \(error.localizedDescription)")
        }

        NSApp.terminate(nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
