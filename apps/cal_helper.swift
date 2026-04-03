// cal_helper.swift
// Drop-in replacement for CalHelper.app that accepts an optional
// command-line argument: --start=YYYY-MM-DD (defaults to today).
// Fetches events from that start date through 2 years out.
// Outputs in the same ||| delimited format as the original.
//
// Build:
//   swiftc cal_helper.swift -o CalHelper -framework EventKit -framework Foundation
// Then copy into CalHelper.app/Contents/MacOS/CalHelper

import Foundation
import EventKit
import AppKit

// ── Parse optional --start= argument ──────────────────────────────────────────
var startOverride: Date? = nil
for arg in CommandLine.arguments.dropFirst() {
    if arg.hasPrefix("--start=") {
        let val = String(arg.dropFirst("--start=".count))
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        df.locale = Locale(identifier: "en_US_POSIX")
        startOverride = df.date(from: val)
    }
}

// ── Shared state ───────────────────────────────────────────────────────────────
let outputFile = "/tmp/cal_helper_output.txt"
let store = EKEventStore()
let sema = DispatchSemaphore(value: 0)
var pendingURLAction: URL? = nil

// ── AppDelegate ────────────────────────────────────────────────────────────────
class AppDelegate: NSObject, NSApplicationDelegate {

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Check for a pending URL from open -u / registered URL scheme
        // (handled via application:openURL:)
        // First, request calendar access
        store.requestFullAccessToEvents { granted, error in
            if !granted {
                self.writeOutput("ERROR:Calendar access denied")
                NSApp.terminate(nil)
                return
            }
            if let url = pendingURLAction {
                self.handleURL(url)
            } else {
                self.fetchAndWrite()
            }
        }
    }

    func application(_ app: NSApplication, open urls: [URL]) {
        if urls.count > 0 {
            pendingURLAction = urls[0]
        }
    }

    // ── Default fetch: start (Jan 1 this year or today) → +2 years ────────────
    func fetchAndWrite() {
        let cal = Calendar.current
        let now = Date()

        let start: Date
        if let override = startOverride {
            start = override
        } else {
            // Default: Jan 1 of current year
            var comps = cal.dateComponents([.year], from: now)
            comps.month = 1; comps.day = 1
            comps.hour = 0; comps.minute = 0; comps.second = 0
            start = cal.date(from: comps) ?? now
        }

        // End: 2 years from today
        let end = cal.date(byAdding: .year, value: 2, to: now) ?? now

        let pred = store.predicateForEvents(withStart: start, end: end, calendars: nil)
        let events = store.events(matching: pred).sorted { $0.startDate < $1.startDate }

        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd HH:mm"
        df.locale = Locale(identifier: "en_US_POSIX")

        var lines: [String] = []
        for evt in events {
            let calName = evt.calendar?.title ?? "Calendar"
            let title = (evt.title ?? "(no title)")
                .replacingOccurrences(of: "|||", with: " ")
            let startStr = df.string(from: evt.startDate)
            let endStr = df.string(from: evt.endDate)
            let allDay = evt.isAllDay ? "1" : "0"
            let location = (evt.location ?? "").replacingOccurrences(of: "|||", with: " ")
            let eventId = evt.eventIdentifier ?? ""
            lines.append("\(calName)|||\(title)|||\(startStr)|||\(endStr)|||\(allDay)|||\(location)|||\(eventId)")
        }

        writeOutput(lines.joined(separator: "\n"))
        NSApp.terminate(nil)
    }

    // ── URL scheme handler (edit / delete / add — unchanged from original) ──────
    func handleURL(_ url: URL) {
        guard let comps = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            writeOutput("ERROR:Bad URL"); NSApp.terminate(nil); return
        }
        let cmd = comps.host ?? ""
        let params = Dictionary(
            uniqueKeysWithValues: (comps.queryItems ?? []).compactMap { item -> (String, String)? in
                guard let val = item.value else { return nil }
                return (item.name, val)
            }
        )

        switch cmd {
        case "add":
            handleAdd(params)
        case "edit":
            handleEdit(params)
        case "delete":
            handleDelete(params)
        default:
            writeOutput("ERROR:Unknown command: \(cmd)")
            NSApp.terminate(nil)
        }
    }

    func handleAdd(_ p: [String: String]) {
        guard let title = p["title"], !title.isEmpty else {
            writeOutput("ERROR:Missing title parameter"); NSApp.terminate(nil); return
        }
        guard let startStr = p["start"], let endStr = p["end"] else {
            writeOutput("ERROR:Missing or invalid start/end. Use yyyy-MM-ddTHH:mm")
            NSApp.terminate(nil); return
        }
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd'T'HH:mm"
        guard let startDate = df.date(from: startStr), let endDate = df.date(from: endStr) else {
            writeOutput("ERROR:Missing or invalid start/end. Use yyyy-MM-ddTHH:mm")
            NSApp.terminate(nil); return
        }
        let event = EKEvent(eventStore: store)
        event.title = title
        event.startDate = startDate
        event.endDate = endDate
        event.calendar = store.defaultCalendarForNewEvents
        if let loc = p["location"] { event.location = loc }
        do {
            try store.save(event, span: .thisEvent, commit: true)
            writeOutput("OK:Event created: \(event.eventIdentifier ?? "")")
        } catch {
            writeOutput("ERROR:Failed to create: \(error.localizedDescription)")
        }
        NSApp.terminate(nil)
    }

    func handleEdit(_ p: [String: String]) {
        guard let eid = p["id"], !eid.isEmpty else {
            writeOutput("ERROR:Missing id parameter"); NSApp.terminate(nil); return
        }
        guard let event = store.event(withIdentifier: eid) else {
            writeOutput("ERROR:Event not found: \(eid)"); NSApp.terminate(nil); return
        }
        if let title = p["title"] { event.title = title }
        if let loc = p["location"] { event.location = loc }
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd'T'HH:mm"
        if let startStr = p["start"], let startDate = df.date(from: startStr) {
            event.startDate = startDate
        }
        if let endStr = p["end"], let endDate = df.date(from: endStr) {
            event.endDate = endDate
        }
        do {
            try store.save(event, span: .thisEvent, commit: true)
            writeOutput("OK:Event updated: \(eid)")
        } catch {
            writeOutput("ERROR:Failed to update: \(error.localizedDescription)")
        }
        NSApp.terminate(nil)
    }

    func handleDelete(_ p: [String: String]) {
        guard let eid = p["id"], !eid.isEmpty else {
            writeOutput("ERROR:Missing id parameter"); NSApp.terminate(nil); return
        }
        guard let event = store.event(withIdentifier: eid) else {
            writeOutput("ERROR:Event not found: \(eid)"); NSApp.terminate(nil); return
        }
        let span: EKSpan = (p["span"] == "future") ? .futureEvents : .thisEvent
        do {
            try store.remove(event, span: span, commit: true)
            writeOutput("OK:Deleted: \(eid)")
        } catch {
            writeOutput("ERROR:Failed to delete: \(error.localizedDescription)")
        }
        NSApp.terminate(nil)
    }

    func writeOutput(_ content: String) {
        try? content.write(toFile: outputFile, atomically: true, encoding: .utf8)
    }
}

// ── Main ───────────────────────────────────────────────────────────────────────
let delegate = AppDelegate()
let app = NSApplication.shared
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
