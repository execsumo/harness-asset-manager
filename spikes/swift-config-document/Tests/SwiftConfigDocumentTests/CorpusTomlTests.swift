import XCTest
@testable import SwiftConfigDocument
import TOMLKit

final class TomlKitRoundTripTests: XCTestCase {
    let FIXTURE = """
    # Codex config -- hand written, do not reformat
    model = "gpt-5"

    [mcp_servers.exa]
    command = "npx"
    args = ["-y", "exa-mcp-server"]  # pinned to npx on purpose
    """

    func test_untouched_document_fails_verbatim_identity_due_to_comment_loss() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .tomlKit)
        let rendered = try dump_config_document(document, file_format: "toml")
        
        // TOMLKit strips all comments and reformats quotes/spacing
        XCTAssertFalse(rendered.contains("# Codex config -- hand written, do not reformat"), "TOMLKit strips top-level comments")
        XCTAssertFalse(rendered.contains("# pinned to npx on purpose"), "TOMLKit strips inline comments")
        XCTAssertNotEqual(rendered, FIXTURE, "TOMLKit fails verbatim round trip")
    }

    func test_comments_survive_an_added_table_fails_in_tomlkit() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .tomlKit)
        var mcp = document["mcp_servers"]?.object ?? [:]
        mcp["context7"] = ["command": "npx", "args": ["-y", "c7"]]
        document["mcp_servers"] = .object(mcp)

        let rendered = try dump_config_document(document, file_format: "toml")
        XCTAssertFalse(rendered.contains("# Codex config -- hand written, do not reformat"))
        XCTAssertFalse(rendered.contains("# pinned to npx on purpose"))
    }

    func test_untouched_array_keeps_its_inline_style_fails_in_tomlkit() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .tomlKit)
        document["model"] = "gpt-5-codex"
        let rendered = try dump_config_document(document, file_format: "toml")
        // TOMLKit emits `[ '-y', 'exa-mcp-server' ]` (single quotes and spaces) instead of `["-y", "exa-mcp-server"]`
        XCTAssertFalse(rendered.contains("args = [\"-y\", \"exa-mcp-server\"]"))
    }

    func test_comments_survive_a_removed_table_fails_in_tomlkit() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .tomlKit)
        var mcp = document["mcp_servers"]?.object ?? [:]
        mcp.removeValue(forKey: "exa")
        document["mcp_servers"] = .object(mcp)
        let rendered = try dump_config_document(document, file_format: "toml")
        XCTAssertFalse(rendered.contains("# Codex config -- hand written, do not reformat"))
    }

    func test_malformed_document_is_reported_not_silently_emptied() {
        XCTAssertThrowsError(try load_config_document("model = = 1", file_format: "toml")) { error in
            guard let configError = error as? ConfigDocumentError else {
                XCTFail("Expected ConfigDocumentError, got \(error)")
                return
            }
            XCTAssertTrue(configError.message.contains("not valid TOML"))
        }
    }
}

final class TomlSurgicalRoundTripTests: XCTestCase {
    let FIXTURE = """
    # Codex config -- hand written, do not reformat
    model = "gpt-5"

    [mcp_servers.exa]
    command = "npx"
    args = ["-y", "exa-mcp-server"]  # pinned to npx on purpose
    """

    func test_untouched_document_is_returned_verbatim() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .surgical)
        let rendered = try dump_config_document(document, file_format: "toml")
        XCTAssertEqual(rendered, FIXTURE)
    }

    func test_dump_is_idempotent() throws {
        let once = try dump_config_document(load_config_document(FIXTURE, file_format: "toml", tomlBackend: .surgical), file_format: "toml")
        let twice = try dump_config_document(load_config_document(once, file_format: "toml", tomlBackend: .surgical), file_format: "toml")
        XCTAssertEqual(once, twice)
    }

    func test_comments_survive_an_added_table() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .surgical)
        var mcp = document["mcp_servers"]?.object ?? [:]
        mcp["context7"] = ["command": "npx", "args": ["-y", "c7"]]
        document["mcp_servers"] = .object(mcp)

        let rendered = try dump_config_document(document, file_format: "toml")
        XCTAssertTrue(rendered.contains("# Codex config -- hand written, do not reformat"))
        XCTAssertTrue(rendered.contains("# pinned to npx on purpose"))
    }

    func test_untouched_array_keeps_its_inline_style() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .surgical)
        document["model"] = "gpt-5-codex"
        let rendered = try dump_config_document(document, file_format: "toml")
        XCTAssertTrue(rendered.contains("args = [\"-y\", \"exa-mcp-server\"]  # pinned to npx on purpose"))
    }

    func test_comments_survive_a_removed_table() throws {
        let document = try load_config_document(FIXTURE, file_format: "toml", tomlBackend: .surgical)
        var mcp = document["mcp_servers"]?.object ?? [:]
        mcp.removeValue(forKey: "exa")
        document["mcp_servers"] = .object(mcp)

        let rendered = try dump_config_document(document, file_format: "toml")
        XCTAssertTrue(rendered.contains("# Codex config -- hand written, do not reformat"))
        XCTAssertFalse(rendered.contains("exa-mcp-server"))
    }

    func test_absent_file_produces_a_writable_document() throws {
        let document = try empty_config_document("toml")
        document["mcp_servers"] = ["exa": ["command": "npx"]]
        let rendered = try dump_config_document(document, file_format: "toml")
        let reloaded = try load_config_document(rendered, file_format: "toml")
        XCTAssertEqual(reloaded["mcp_servers"]?["exa"]?["command"], "npx")
    }
}
