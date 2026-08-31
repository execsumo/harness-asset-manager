import Foundation
@testable import SwiftConfigDocument

func fixtureURL(named filename: String, filePath: String = #filePath) -> URL {
    let currentFile = URL(fileURLWithPath: filePath)
    let packageRoot = currentFile.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    let urlFromPath = packageRoot.appendingPathComponent("Fixtures").appendingPathComponent(filename)
    if FileManager.default.fileExists(atPath: urlFromPath.path) {
        return urlFromPath
    }
    let cwdURL = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    let urlFromCWD = cwdURL.appendingPathComponent("Fixtures").appendingPathComponent(filename)
    if FileManager.default.fileExists(atPath: urlFromCWD.path) {
        return urlFromCWD
    }
    return cwdURL.appendingPathComponent("spikes/swift-config-document/Fixtures").appendingPathComponent(filename)
}

func loadFixtureText(named filename: String, filePath: String = #filePath) throws -> String {
    let url = fixtureURL(named: filename, filePath: filePath)
    let data = try Data(contentsOf: url)
    guard let text = String(data: data, encoding: .utf8) else {
        throw ConfigDocumentError("Failed to decode fixture \(filename) as UTF-8")
    }
    return text
}
