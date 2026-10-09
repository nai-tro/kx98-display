import Foundation

typealias MRCallback = @convention(block) (NSDictionary?) -> Void
typealias MRGetNowPlayingInfo = @convention(c) (DispatchQueue, MRCallback) -> Void

guard let handle = dlopen("/System/Library/PrivateFrameworks/MediaRemote.framework/MediaRemote", RTLD_NOW),
      let sym = dlsym(handle, "MRMediaRemoteGetNowPlayingInfo") else {
    print("{\"playing\":false}")
    exit(0)
}

let getInfo = unsafeBitCast(sym, to: MRGetNowPlayingInfo.self)
var done = false
var res: [String: Any] = ["playing": false]

let handler: MRCallback = { dict in
    if let dict = dict {
        let title = (dict["kMRMediaRemoteNowPlayingInfoTitle"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let artist = (dict["kMRMediaRemoteNowPlayingInfoArtist"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let album = (dict["kMRMediaRemoteNowPlayingInfoAlbum"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let rate = (dict["kMRMediaRemoteNowPlayingInfoPlaybackRate"] as? NSNumber)?.doubleValue ?? 0.0
        
        let isPlaying = (rate > 0.0 && !title.isEmpty)
        res = [
            "playing": isPlaying,
            "title": title,
            "artist": artist,
            "album": album
        ]
    }
    done = true
}

getInfo(DispatchQueue.main, handler)

let timeout = Date().addingTimeInterval(1.0)
while !done && Date() < timeout {
    RunLoop.current.run(until: Date().addingTimeInterval(0.02))
}

if let data = try? JSONSerialization.data(withJSONObject: res), let s = String(data: data, encoding: .utf8) {
    print(s)
} else {
    print("{\"playing\":false}")
}
