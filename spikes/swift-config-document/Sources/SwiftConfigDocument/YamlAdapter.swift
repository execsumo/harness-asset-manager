import Foundation
import Yams

/// Candidate adapter using Yams (wraps libyaml).
/// This evaluates Yams' native behavior against the round-trip preservation bar.
public final class YamsDocument: @unchecked Sendable {
    public var node: Node?
    private let originalText: String

    public init(node: Node? = nil, originalText: String = "") {
        self.node = node
        self.originalText = originalText
    }

    public static func parse(text: String) throws -> YamsDocument {
        do {
            let node = try Yams.compose(yaml: text)
            return YamsDocument(node: node, originalText: text)
        } catch {
            throw ConfigDocumentError("not valid YAML: \(error)")
        }
    }

    public func dumps() throws -> String {
        guard let node = node else { return "" }
        do {
            return try Yams.serialize(node: node)
        } catch {
            throw ConfigDocumentError("failed to serialize YAML: \(error)")
        }
    }
}
