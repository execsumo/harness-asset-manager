import XCTest
@testable import SwiftConfigDocument

final class PressureAdversarialTests: XCTestCase {
    
    // MARK: - 1. Heavily Commented Codex Config (~/.codex/config.toml)
    
    func test_codex_config_tomlkit_regression_destroys_all_comments() throws {
        let text = try loadFixtureText(named: "codex_config.toml")
        let doc = try load_config_document(text, file_format: "toml", tomlBackend: .tomlKit)
        
        // Mutate an MCP server
        var mcp = doc["mcp_servers"]?.object ?? [:]
        mcp["context7"] = ["command": "npx", "args": ["-y", "c7"]]
        doc["mcp_servers"] = .object(mcp)
        
        let rendered = try dump_config_document(doc, file_format: "toml")
        
        // Critical finding: TOMLKit drops every comment from the file
        XCTAssertFalse(rendered.contains("# Codex configuration file"), "Regression: TOMLKit deleted header comments")
        XCTAssertFalse(rendered.contains("# Primary model"), "Regression: TOMLKit deleted inline comment")
        XCTAssertFalse(rendered.contains("# Core editor settings"), "Regression: TOMLKit deleted section comment")
        XCTAssertFalse(rendered.contains("# Required for web search capabilities"), "Regression: TOMLKit deleted server comment")
        XCTAssertFalse(rendered.contains("# Hooks configuration"), "Regression: TOMLKit deleted hooks comment")
    }

    func test_codex_config_surgical_preserves_all_comments_and_formatting() throws {
        let text = try loadFixtureText(named: "codex_config.toml")
        let doc = try load_config_document(text, file_format: "toml", tomlBackend: .surgical)
        
        // Mutate an MCP server
        var mcp = doc["mcp_servers"]?.object ?? [:]
        mcp["context7"] = ["command": "npx", "args": ["-y", "c7"]]
        doc["mcp_servers"] = .object(mcp)
        
        let rendered = try dump_config_document(doc, file_format: "toml")
        
        // Surgical approach preserves all comments
        XCTAssertTrue(rendered.contains("# Codex configuration file"), "Surgical preserves header comments")
        XCTAssertTrue(rendered.contains("# Primary model"), "Surgical preserves inline comment")
        XCTAssertTrue(rendered.contains("# Core editor settings"), "Surgical preserves section comment")
        XCTAssertTrue(rendered.contains("# Required for web search capabilities"), "Surgical preserves server comment")
        XCTAssertTrue(rendered.contains("# Hooks configuration"), "Surgical preserves hooks comment")
        XCTAssertTrue(rendered.contains("[mcp_servers.context7]"), "Surgical appends new table cleanly")
    }

    // MARK: - 2. Advanced YAML (anchors, aliases, block scalars, nested comments)
    
    func test_advanced_yaml_yams_destroys_all_comments_and_anchors() throws {
        let text = try loadFixtureText(named: "adversarial_yaml.yaml")
        let doc = try load_config_document(text, file_format: "yaml")
        
        // Mutate model
        doc["model"] = "claude-3-7-sonnet-latest"
        
        let rendered = try dump_config_document(doc, file_format: "yaml")
        
        // Critical finding: Yams (libyaml) discards comments, anchors, and original block scalar styles
        XCTAssertFalse(rendered.contains("# Hermes Agent Configuration"), "Yams deleted header comments")
        XCTAssertFalse(rendered.contains("# Active reasoning model"), "Yams deleted inline comments")
        XCTAssertFalse(rendered.contains("# Executed before modifying git working tree"), "Yams deleted sequence comments")
        XCTAssertFalse(rendered.contains("&default_env"), "Yams expands anchors instead of preserving them")
    }

    // MARK: - 3. CRLF, UTF-8 BOM, Tabs, Non-ASCII Unicode
    
    func test_jsonc_crlf_bom_unicode_preservation() throws {
        let text = try loadFixtureText(named: "adversarial_crlf_bom_unicode.jsonc")
        let doc = try load_config_document(text, file_format: "jsonc")
        
        // 1. Untouched verbatim preservation
        let untouched = try dump_config_document(doc, file_format: "jsonc")
        XCTAssertEqual(untouched, text, "Untouched CRLF + BOM + Unicode document must be byte-identical")
        
        // 2. Mutation with comment & formatting preservation
        var mcp = doc["mcp"]?.object ?? [:]
        mcp["追加サーバ"] = ["command": ["npx", "extra-tool"]]
        doc["mcp"] = .object(mcp)
        
        let rendered = try dump_config_document(doc, file_format: "jsonc")
        XCTAssertTrue(rendered.contains("// 設定コメント (タブインデント)"), "Unicode tab comment preserved")
        XCTAssertTrue(rendered.contains("/* ブロック"), "Unicode block comment preserved")
        XCTAssertTrue(rendered.contains("café-tool"), "Accented unicode preserved")
        XCTAssertTrue(rendered.contains("🦀"), "Emoji character preserved")
    }

    // MARK: - 4. Advanced TOML (inline tables, multiline strings, dotted keys)
    
    func test_advanced_toml_surgical_preserves_multiline_and_dotted_keys() throws {
        let text = try loadFixtureText(named: "adversarial_toml_advanced.toml")
        let doc = try load_config_document(text, file_format: "toml", tomlBackend: .surgical)
        
        // Mutate title
        doc["title"] = "Updated TOML Spec"
        
        let rendered = try dump_config_document(doc, file_format: "toml")
        
        XCTAssertTrue(rendered.contains("title = \"Updated TOML Spec\""))
        XCTAssertTrue(rendered.contains("# Tests inline tables, multiline strings, dotted keys, and deep nesting."))
        XCTAssertTrue(rendered.contains("# Primary leader node"), "Nested table comment preserved")
    }
}
