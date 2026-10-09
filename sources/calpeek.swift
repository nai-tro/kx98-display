import Foundation
import EventKit

struct EventInfo: Codable {
    let title: String
    let start: String
    let end: String
}

struct CalResult: Codable {
    let busy: Bool
    let current: EventInfo?
    let next: EventInfo?
    let error: String?
}

func isoDate(_ date: Date) -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter.string(from: date)
}

func main() {
    let store = EKEventStore()
    let semaphore = DispatchSemaphore(value: 0)
    var accessGranted = false

    if #available(macOS 14.0, *) {
        store.requestFullAccessToEvents { granted, error in
            accessGranted = granted
            semaphore.signal()
        }
    } else {
        store.requestAccess(to: .event) { granted, error in
            accessGranted = granted
            semaphore.signal()
        }
    }

    _ = semaphore.wait(timeout: .now() + 5.0)

    guard accessGranted else {
        let res = CalResult(busy: false, current: nil, next: nil, error: "access_denied")
        if let data = try? JSONEncoder().encode(res), let s = String(data: data, encoding: .utf8) {
            print(s)
        }
        return
    }

    let now = Date()
    guard let startRange = Calendar.current.date(byAdding: .minute, value: -1, to: now),
          let endRange = Calendar.current.date(byAdding: .hour, value: 12, to: now) else {
        let res = CalResult(busy: false, current: nil, next: nil, error: "range_error")
        if let data = try? JSONEncoder().encode(res), let s = String(data: data, encoding: .utf8) {
            print(s)
        }
        return
    }

    let predicate = store.predicateForEvents(withStart: startRange, end: endRange, calendars: nil)
    let rawEvents = store.events(matching: predicate)

    // Filter events
    let validEvents = rawEvents.filter { event in
        if event.isAllDay { return false }
        if event.status == .canceled { return false }
        if event.availability == .free { return false }

        // Check if user explicitly declined
        if let attendees = event.attendees {
            for attendee in attendees {
                if attendee.isCurrentUser && attendee.participantStatus == .declined {
                    return false
                }
            }
        }
        return true
    }.sorted { $0.startDate < $1.startDate }

    // Find current event (overlapping now)
    var currentEvent: EKEvent? = nil
    for e in validEvents {
        if e.startDate <= now && e.endDate > now {
            currentEvent = e
            break
        }
    }

    // Find next event (starts strictly in future)
    var nextEvent: EKEvent? = nil
    for e in validEvents {
        if e.startDate > now {
            nextEvent = e
            break
        }
    }

    let busy = (currentEvent != nil)

    let currentInfo = currentEvent.map {
        EventInfo(title: $0.title ?? "Event", start: isoDate($0.startDate), end: isoDate($0.endDate))
    }
    let nextInfo = nextEvent.map {
        EventInfo(title: $0.title ?? "Event", start: isoDate($0.startDate), end: isoDate($0.endDate))
    }

    let result = CalResult(busy: busy, current: currentInfo, next: nextInfo, error: nil)
    if let data = try? JSONEncoder().encode(result), let s = String(data: data, encoding: .utf8) {
        print(s)
    }
}

main()
