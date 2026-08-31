import XCTest
@testable import SwiftConfigDocument
import Yams

final class YamlRoundTripTests: XCTestCase {
    let FIXTURE = """
    # Hermes config
    model: big

    mcp_servers:
      exa:
        command: npx  # keep npx
    """

    func test_comments_survive_a_mutation_fails_in_yams() throws {
        let document = try load_config_document(FIXTURE, file_format: "yaml")
        var mcp = document["mcp_servers"]?.object ?? [:]
        mcp["context7"] = ["command": "npx"]
        document["mcp_servers"] = .object(mcp)

        let rendered = try dump_config_document(document, file_format: "yaml")
        
        // Yams (libyaml) discards comments at parse time
        XCTAssertFalse(rendered.contains("# Hermes config"), "Yams strips top-level comments")
        XCTAssertFalse(rendered.contains("# keep npx"), "Yams strips inline comments")
        XCTAssertTrue(rendered.contains("context7"), "Mutation is present in output")
    }

    func test_untouched_document_fails_verbatim_identity_in_yams() throws {
        let document = try load_config_document(FIXTURE, file_format: "yaml")
        let rendered = try dump_config_document(document, file_format: "yaml")
        XCTAssertNotEqual(rendered, FIXTURE, "Yams cannot re-emit untouched YAML verbatim")
    }

    func test_malformed_document_is_reported_not_silently_emptied() {
        XCTAssertThrowsError(try load_config_document("a:\n- b\n  c: [", file_format: "yaml")) { error in
            guard let configError = error as? ConfigDocumentError else {
                XCTFail("Expected ConfigDocumentError, got \(error)")
                return
            }
            XCTAssertTrue(configError.message.contains("not valid YAML"))
        }
    }
}
