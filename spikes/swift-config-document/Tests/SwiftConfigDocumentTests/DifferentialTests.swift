import XCTest
@testable import SwiftConfigDocument

final class DifferentialTests: XCTestCase {

    func test_jsonc_differential_fidelity_against_python_baseline() throws {
        let fixture = try loadFixtureText(named: "opencode.jsonc")
        
        // 1. Untouched
        let doc = try load_config_document(fixture, file_format: "jsonc")
        let untouched = try dump_config_document(doc, file_format: "jsonc")
        XCTAssertEqual(untouched, fixture, "JSONC untouched Swift dump matches Python baseline exactly (0 bytes diff)")
        
        // 2. Mutation (remove MCP entry)
        var mcp = doc["mcp"]?.object ?? [:]
        mcp.removeValue(forKey: "exa")
        doc["mcp"] = .object(mcp)
        let removed = try dump_config_document(doc, file_format: "jsonc")
        
        // Expected Python output:
        let expectedPythonOutput = """
        {
          // My OpenCode config -- hand written
          "theme": "dark",
          "mcp": {},
          /* keep this one until the API key rotates */
          "model": "big"
        }
        """
        XCTAssertEqual(removed.trimmingCharacters(in: .whitespacesAndNewlines),
                       expectedPythonOutput.trimmingCharacters(in: .whitespacesAndNewlines),
                       "JSONC removal output matches Python config_document.py exactly")
    }

    func test_toml_differential_candidates_classification() throws {
        let fixture = try loadFixtureText(named: "codex_config.toml")
        
        // Candidate 1: TOMLKit
        let tomlKitDoc = try load_config_document(fixture, file_format: "toml", tomlBackend: .tomlKit)
        let tomlKitOut = try dump_config_document(tomlKitDoc, file_format: "toml")
        XCTAssertFalse(tomlKitOut.contains("# Codex configuration file"), "TOMLKit is DESTRUCTIVE: deletes all comments")
        
        // Candidate 2: Surgical Engine
        let surgicalDoc = try load_config_document(fixture, file_format: "toml", tomlBackend: .surgical)
        let surgicalOut = try dump_config_document(surgicalDoc, file_format: "toml")
        XCTAssertEqual(surgicalOut, fixture, "TOML Surgical Engine is IDENTICAL on untouched files")
        
        // Mutation with surgical engine
        var mcp = surgicalDoc["mcp_servers"]?.object ?? [:]
        mcp.removeValue(forKey: "exa")
        surgicalDoc["mcp_servers"] = .object(mcp)
        let mutatedSurgicalOut = try dump_config_document(surgicalDoc, file_format: "toml")
        XCTAssertTrue(mutatedSurgicalOut.contains("# Codex configuration file"), "Surgical preserves comments across mutations")
        XCTAssertTrue(mutatedSurgicalOut.contains("# Core editor settings"), "Surgical preserves section comments")
    }

    func test_yaml_differential_yams_classification() throws {
        let fixture = try loadFixtureText(named: "adversarial_yaml.yaml")
        let doc = try load_config_document(fixture, file_format: "yaml")
        let out = try dump_config_document(doc, file_format: "yaml")
        
        // Yams is DESTRUCTIVE
        XCTAssertFalse(out.contains("# Hermes Agent Configuration"), "Yams is DESTRUCTIVE: deletes comments")
        XCTAssertFalse(out.contains("# Active reasoning model"), "Yams is DESTRUCTIVE: deletes inline comments")
    }
}
