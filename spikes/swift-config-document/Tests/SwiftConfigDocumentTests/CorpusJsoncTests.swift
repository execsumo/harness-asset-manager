import XCTest
@testable import SwiftConfigDocument

final class JsoncCommentBlankingTests: XCTestCase {
    func test_blanking_preserves_offsets() {
        let text = "{\n  // note\n  \"a\": 1\n}"
        XCTAssertEqual(blank_jsonc_comments(text).count, text.count)
    }

    func test_comment_marker_inside_a_string_is_not_a_comment() throws {
        let source = "{\"note\": \"use // to comment\", \"a\": 1}"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        XCTAssertEqual(document["note"], "use // to comment")
        XCTAssertEqual(document["a"], 1)
    }

    func test_block_comment_marker_inside_a_string_is_not_a_comment() throws {
        let source = "{\"re\": \"a/*b*/c\"}"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        XCTAssertEqual(document["re"], "a/*b*/c")
    }

    func test_trailing_comma_shape_inside_a_string_is_not_a_trailing_comma() throws {
        let source = "{\"s\": \"trailing, }\"}"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        XCTAssertEqual(document["s"], "trailing, }")
    }

    func test_escaped_quote_does_not_end_the_string() throws {
        let source = "{\"esc\": \"a\\\"// b\", \"x\": 1}"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        XCTAssertEqual(document["esc"], "a\"// b")
        XCTAssertEqual(document["x"], 1)
    }

    func test_real_comments_and_trailing_commas_are_still_removed() throws {
        let source = """
        {
          // line comment
          "a": 1,
          /* block
             comment */
          "b": [1, 2,],
        }
        """
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        XCTAssertEqual(document["a"], 1)
        XCTAssertEqual(document["b"], [1, 2])
    }

    func test_unterminated_block_comment_does_not_hang() throws {
        let document = try JsoncDocument.parse(text: "{\"a\": 1}\n/* dangling", isJsonc: true)
        XCTAssertEqual(document["a"], 1)
    }
}

final class JsoncRoundTripTests: XCTestCase {
    let FIXTURE = """
    {
      // My OpenCode config -- hand written
      "theme": "dark",
      "mcp": {
        "exa": { "type": "local", "command": ["npx", "exa"] }
      },
      /* keep this one until the API key rotates */
      "model": "big"
    }
    """

    private func roundTrip(_ doc: JsoncDocument) -> String {
        return doc.dumps()
    }

    func test_untouched_document_is_returned_verbatim() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        XCTAssertEqual(roundTrip(document), FIXTURE)
    }

    func test_dump_is_idempotent() throws {
        let once = roundTrip(try JsoncDocument.parse(text: FIXTURE, isJsonc: true))
        let twice = roundTrip(try JsoncDocument.parse(text: once, isJsonc: true))
        XCTAssertEqual(once, twice)
    }

    func test_comments_survive_an_added_subtree_entry() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        var mcp = document["mcp"]?.object ?? [:]
        mcp["context7"] = ["type": "local", "command": ["npx", "c7"]]
        document["mcp"] = .object(mcp)

        let rendered = roundTrip(document)
        XCTAssertTrue(rendered.contains("// My OpenCode config -- hand written"))
        XCTAssertTrue(rendered.contains("/* keep this one until the API key rotates */"))

        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(reparsed["mcp"]?["context7"]?["command"], ["npx", "c7"])
    }

    func test_comments_survive_a_removed_subtree_entry() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        var mcp = document["mcp"]?.object ?? [:]
        mcp.removeValue(forKey: "exa")
        document["mcp"] = .object(mcp)

        let rendered = roundTrip(document)
        XCTAssertTrue(rendered.contains("// My OpenCode config -- hand written"))
        XCTAssertTrue(rendered.contains("/* keep this one until the API key rotates */"))

        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(reparsed["mcp"], [:])
    }

    func test_untouched_keys_keep_their_original_formatting() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        var mcp = document["mcp"]?.object ?? [:]
        mcp["exa"] = ["type": "local", "command": ["npx", "exa", "--v2"]]
        document["mcp"] = .object(mcp)

        let rendered = roundTrip(document)
        XCTAssertTrue(rendered.contains("  \"theme\": \"dark\","))
        XCTAssertTrue(rendered.contains("  \"model\": \"big\""))
    }

    func test_added_top_level_key_adopts_the_document_indentation() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        document["hooks"] = ["beforeShell": []]

        let rendered = roundTrip(document)
        XCTAssertTrue(rendered.contains("\n  \"hooks\": {"))
        XCTAssertTrue(rendered.contains("// My OpenCode config -- hand written"))
    }

    func test_written_output_is_valid_json_once_comments_are_stripped() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        var mcp = document["mcp"]?.object ?? [:]
        mcp["context7"] = ["type": "local"]
        document["mcp"] = .object(mcp)
        document["theme"] = nil

        let rendered = roundTrip(document)
        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(
            reparsed.value,
            [
                "mcp": [
                    "exa": ["type": "local", "command": ["npx", "exa"]],
                    "context7": ["type": "local"]
                ],
                "model": "big"
            ]
        )
    }

    func test_trailing_comment_survives_an_appended_key() throws {
        let source = "{\n  \"a\": 1  // muscle memory\n}\n"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        document["b"] = 2
        let rendered = roundTrip(document)
        XCTAssertTrue(rendered.contains("// muscle memory"))
        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(reparsed.value, ["a": 1, "b": 2])
    }

    func test_comment_about_a_kept_key_survives_removal_of_the_next_key() throws {
        let source = "{\n  \"a\": 1,  // about a\n  \"b\": 2\n}\n"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        document["b"] = nil
        let rendered = roundTrip(document)
        XCTAssertTrue(rendered.contains("// about a"))
        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(reparsed.value, ["a": 1])
    }

    func test_removed_key_on_a_shared_line_does_not_drag_its_neighbour_back() throws {
        let source = "{\"a\": 1, \"b\": 2}"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        document["b"] = nil
        let rendered = roundTrip(document)
        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(reparsed.value, ["a": 1])
    }

    func test_add_then_remove_returns_the_file_to_its_original_shape() throws {
        let added = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        var mcp = added["mcp"]?.object ?? [:]
        mcp["context7"] = ["type": "local"]
        added["mcp"] = .object(mcp)
        let intermediate = roundTrip(added)

        let removed = try JsoncDocument.parse(text: intermediate, isJsonc: true)
        var remMcp = removed["mcp"]?.object ?? [:]
        remMcp.removeValue(forKey: "context7")
        removed["mcp"] = .object(remMcp)
        let final = roundTrip(removed)

        let parsedFinal = try JsoncDocument.parse(text: final, isJsonc: true)
        let parsedFixture = try JsoncDocument.parse(text: FIXTURE, isJsonc: true)
        XCTAssertEqual(parsedFinal.value, parsedFixture.value)
        XCTAssertTrue(final.contains("// My OpenCode config -- hand written"))
        XCTAssertTrue(final.contains("/* keep this one until the API key rotates */"))
    }

    func test_single_line_object_gains_a_key_without_breaking() throws {
        let source = "{\"mcp\": {\"a\": 1}}"
        let document = try JsoncDocument.parse(text: source, isJsonc: true)
        var mcp = document["mcp"]?.object ?? [:]
        mcp["b"] = 2
        document["mcp"] = .object(mcp)
        let rendered = roundTrip(document)
        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(reparsed.value, ["mcp": ["a": 1, "b": 2]])
    }

    func test_absent_file_produces_a_writable_document() throws {
        let document = JsoncDocument()
        document["mcp"] = ["exa": ["type": "local"]]
        let rendered = roundTrip(document)
        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: true)
        XCTAssertEqual(reparsed.value, ["mcp": ["exa": ["type": "local"]]])
    }

    func test_malformed_document_is_reported_not_silently_emptied() {
        XCTAssertThrowsError(try JsoncDocument.parse(text: "{\"a\": ", isJsonc: true)) { error in
            guard let configError = error as? ConfigDocumentError else {
                XCTFail("Expected ConfigDocumentError, got \(error)")
                return
            }
            XCTAssertTrue(configError.message.contains("not valid JSONC"))
        }
    }
}
