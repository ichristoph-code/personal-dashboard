import Cocoa
import EventKit

let store = EKEventStore()
let outputPath = "/tmp/cal_helper_output.txt"

func writeOutput(_ text: String) {
    try? text.write(toFile: outputPath, atomically: true, encoding: .utf8)
}

/// Ensure we have calendar access; returns true if granted
func ensureAccess() -> Bool {
    let status = EKEventStore.authorizationStatus(for: .event)
    if status == .authorized || status == .fullAccess {
        return true
    } else if status == .notDetermined {
        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        store.requestFullAccessToEvents { g, _ in
            granted = g
            semaphore.signal()
        }
        semaphore.wait()
        return granted
    }
    return false
}

/// Find an event by its external identifier within the next 2 years
func findEvent(byId eventId: String) -> EKEvent? {
    let now = Date()
    let calendar = Calendar.current
    let start = calendar.date(byAdding: .day, value: -1, to: now)!
    let year = calendar.component(.year, from: now)
    let end = calendar.date(from: DateComponents(year: year + 2, month: 1, day: 1))!
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
    let events = store.events(matching: predicate)
    return events.first { $0.calendarItemExternalIdentifier == eventId }
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
                self.runReadMode()
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
        switch command {
        case "add":
            handleAddEvent(url: url)
        case "edit":
            handleEditEvent(url: url)
        case "delete":
            handleDeleteEvent(url: url)
        default:
            writeOutput("ERROR:Unknown command: \(command)")
        }
        NSApp.terminate(nil)
    }

    // MARK: - URL Command Helpers

    func parseParams(from url: URL) -> [String: String]? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let queryItems = components.queryItems else { return nil }
        return Dictionary(uniqueKeysWithValues: queryItems.compactMap { item in
            item.value.map { (item.name, $0) }
        })
    }

    func parseDatetime(_ str: String) -> Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        return formatter.date(from: str)
    }

    // MARK: - Add Event

    func handleAddEvent(url: URL) {
        guard let params = parseParams(from: url) else {
            writeOutput("ERROR:Missing query parameters"); return
        }
        guard let title = params["title"], !title.isEmpty else {
            writeOutput("ERROR:Missing title parameter"); return
        }
        guard let startStr = params["start"], let endStr = params["end"],
              let startDate = parseDatetime(startStr), let endDate = parseDatetime(endStr) else {
            writeOutput("ERROR:Missing or invalid start/end. Use yyyy-MM-ddTHH:mm"); return
        }

        guard ensureAccess() else {
            writeOutput("ERROR:Calendar access denied"); return
        }

        let event = EKEvent(eventStore: store)
        event.title = title
        event.startDate = startDate
        event.endDate = endDate
        if let loc = params["location"], !loc.isEmpty { event.location = loc }
        event.calendar = store.defaultCalendarForNewEvents

        do {
            try store.save(event, span: .thisEvent)
            writeOutput("OK:Event created: \(title)")
        } catch {
            writeOutput("ERROR:Failed to save: \(error.localizedDescription)")
        }
    }

    // MARK: - Edit Event

    func handleEditEvent(url: URL) {
        guard let params = parseParams(from: url) else {
            writeOutput("ERROR:Missing query parameters"); return
        }
        guard let eventId = params["id"], !eventId.isEmpty else {
            writeOutput("ERROR:Missing id parameter"); return
        }
        guard ensureAccess() else {
            writeOutput("ERROR:Calendar access denied"); return
        }
        guard let event = findEvent(byId: eventId) else {
            writeOutput("ERROR:Event not found: \(eventId)"); return
        }

        // Update only the fields that were provided
        if let title = params["title"], !title.isEmpty { event.title = title }
        if let startStr = params["start"], let d = parseDatetime(startStr) { event.startDate = d }
        if let endStr = params["end"], let d = parseDatetime(endStr) { event.endDate = d }
        if let loc = params["location"] { event.location = loc.isEmpty ? nil : loc }

        do {
            try store.save(event, span: .thisEvent)
            writeOutput("OK:Event updated: \(event.title ?? "")")
        } catch {
            writeOutput("ERROR:Failed to update: \(error.localizedDescription)")
        }
    }

    // MARK: - Delete Event

    func handleDeleteEvent(url: URL) {
        guard let params = parseParams(from: url) else {
            writeOutput("ERROR:Missing query parameters"); return
        }
        guard let eventId = params["id"], !eventId.isEmpty else {
            writeOutput("ERROR:Missing id parameter"); return
        }
        guard ensureAccess() else {
            writeOutput("ERROR:Calendar access denied"); return
        }
        guard let event = findEvent(byId: eventId) else {
            writeOutput("ERROR:Event not found: \(eventId)"); return
        }

        let title = event.title ?? ""
        do {
            try store.remove(event, span: .thisEvent)
            writeOutput("OK:Event deleted: \(title)")
        } catch {
            writeOutput("ERROR:Failed to delete: \(error.localizedDescription)")
        }
    }

    // MARK: - Read Mode

    func runReadMode() {
        guard ensureAccess() else {
            writeOutput("ERROR:Calendar access denied. Grant in System Settings > Privacy & Security > Calendars")
            return
        }
        writeEvents()
    }

    func writeEvents() {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm"

        let now = Date()
        let calendar = Calendar.current
        // Fetch the full current year plus next year for year view
        let year = calendar.component(.year, from: now)
        let endDate = calendar.date(from: DateComponents(year: year + 1, month: 12, day: 31, hour: 23, minute: 59))!

        let predicate = store.predicateForEvents(withStart: now, end: endDate, calendars: nil)
        let events = store.events(matching: predicate)

        var lines: [String] = []
        for event in events {
            let calName = event.calendar.title
            let title = event.title ?? "(No Title)"
            let start = formatter.string(from: event.startDate)
            let end = formatter.string(from: event.endDate)
            let allDay = event.isAllDay ? "1" : "0"
            let location = event.location ?? ""
            let eventId = event.calendarItemExternalIdentifier ?? ""
            lines.append("\(calName)|||\(title)|||\(start)|||\(end)|||\(allDay)|||\(location)|||\(eventId)")
        }
        writeOutput(lines.joined(separator: "\n"))
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
