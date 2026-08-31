import Foundation
import TOMLKit

/// Candidate adapter using TOMLKit (wraps toml++).
/// This evaluates TOMLKit's native behavior against the round-trip preservation bar.
public final class TomlKitDocument: @unchecked Sendable {
    public var table: TOMLTable
    private let originalText: String

    public init(table: TOMLTable = TOMLTable(), originalText: String = "") {
        self.table = table
        self.originalText = originalText
    }

    public static func parse(text: String) throws -> TomlKitDocument {
        do {
            let table = try TOMLTable(string: text)
            return TomlKitDocument(table: table, originalText: text)
        } catch let err as TOMLParseError {
            throw ConfigDocumentError("not valid TOML: \(err)")
        } catch {
            throw ConfigDocumentError("not valid TOML: \(error)")
        }
    }

    public func dumps() -> String {
        return table.convert()
    }
}
