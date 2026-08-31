import XCTest
@testable import SwiftConfigDocument

final class IdempotenceTests: XCTestCase {

    // MARK: - Untouched Idempotence: dump(load(x)) == x byte-for-byte

    func test_jsonc_untouched_idempotence() throws {
        let fixture = """
        {
          // comment 1
          "a": 1,
          /* comment 2 */
          "b": [2, 3]
        }
        """
        let doc = try load_config_document(fixture, file_format: "jsonc")
        let dumped = try dump_config_document(doc, file_format: "jsonc")
        XCTAssertEqual(dumped, fixture, "JSONC dump(load(x)) must be byte-for-byte identical")
    }

    func test_jsonc_crlf_bom_unicode_untouched_idempotence() throws {
        let text = try loadFixtureText(named: "adversarial_crlf_bom_unicode.jsonc")
        let doc = try load_config_document(text, file_format: "jsonc")
        let dumped = try dump_config_document(doc, file_format: "jsonc")
        XCTAssertEqual(dumped, text, "CRLF + BOM + Unicode JSONC dump(load(x)) must be byte-for-byte identical")
    }

    func test_toml_surgical_untouched_idempotence() throws {
        let text = try loadFixtureText(named: "codex_config.toml")
        let doc = try load_config_document(text, file_format: "toml", tomlBackend: .surgical)
        let dumped = try dump_config_document(doc, file_format: "toml")
        XCTAssertEqual(dumped, text, "TOML Surgical dump(load(x)) must be byte-for-byte identical")
    }

    func test_toml_surgical_advanced_untouched_idempotence() throws {
        let text = try loadFixtureText(named: "adversarial_toml_advanced.toml")
        let doc = try load_config_document(text, file_format: "toml", tomlBackend: .surgical)
        let dumped = try dump_config_document(doc, file_format: "toml")
        XCTAssertEqual(dumped, text, "Advanced TOML Surgical dump(load(x)) must be byte-for-byte identical")
    }

    // MARK: - Mutated Stability: dump(load(dump(load(x_mutated)))) == dump(load(x_mutated))

    func test_jsonc_mutated_stability() throws {
        let text = try loadFixtureText(named: "adversarial_crlf_bom_unicode.jsonc")
        let doc1 = try load_config_document(text, file_format: "jsonc")
        var mcp = doc1["mcp"]?.object ?? [:]
        mcp["added"] = ["command": ["echo", "hi"]]
        doc1["mcp"] = .object(mcp)

        let dump1 = try dump_config_document(doc1, file_format: "jsonc")
        
        let doc2 = try load_config_document(dump1, file_format: "jsonc")
        let dump2 = try dump_config_document(doc2, file_format: "jsonc")
        
        XCTAssertEqual(dump1, dump2, "JSONC mutated output must be stable on subsequent load/dump cycles")
    }

    func test_toml_surgical_mutated_stability() throws {
        let text = try loadFixtureText(named: "codex_config.toml")
        let doc1 = try load_config_document(text, file_format: "toml", tomlBackend: .surgical)
        doc1["model"] = "gpt-5-turbo"
        
        let dump1 = try dump_config_document(doc1, file_format: "toml")
        
        let doc2 = try load_config_document(dump1, file_format: "toml", tomlBackend: .surgical)
        let dump2 = try dump_config_document(doc2, file_format: "toml")
        
        XCTAssertEqual(dump1, dump2, "TOML Surgical mutated output must be stable on subsequent load/dump cycles")
    }
}
