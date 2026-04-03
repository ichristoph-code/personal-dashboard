#!/usr/bin/env swift
// Fetches calendar events from Jan 1 of the current year up to (but not including) today.
// Outputs in the same ||| delimited format as CalHelper.app.
// Usage: swift fetch_past_events.swift > /tmp/past_events.txt

import Foundation
import EventKit

let store = EKEventStore()
let sema = DispatchSemaphore(value: 0)

store.requestFullAccessToEvents { granted, error in
    guard granted else {
        print("ERROR:Calendar access denied")
        sema.signal()
        return
    }

    let cal = Calendar.current
    let now = Date()

    // Start: Jan 1 of this year
    var startComps = cal.dateComponents([.year], from: now)
    startComps.month = 1; startComps.day = 1
    startComps.hour = 0; startComps.minute = 0; startComps.second = 0
    let startDate = cal.date(from: startComps)!

    // End: start of today (yesterday and before only)
    let endDate = cal.startOfDay(for: now)

    // Don't run if we're already at Jan 1
    guard startDate < endDate else {
        sema.signal()
        return
    }

    let pred = store.predicateForEvents(withStart: startDate, end: endDate, calendars: nil)
    let events = store.events(matching: pred)

    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd HH:mm"
    df.locale = Locale(identifier: "en_US_POSIX")

    for evt in events {
        let calName = evt.calendar?.title ?? "Calendar"
        let title = evt.title ?? "(no title)"
        let start = df.string(from: evt.startDate)
        let end = df.string(from: evt.endDate)
        let allDay = evt.isAllDay ? "1" : "0"
        let location = evt.location ?? ""
        let eventId = evt.eventIdentifier ?? ""
        print("\(calName)|||\(title)|||\(start)|||\(end)|||\(allDay)|||\(location)|||\(eventId)")
    }

    sema.signal()
}

sema.wait()
