import XCTest
@testable import SwiftConfigDocument

final class SubtreeFactoryTests: XCTestCase {
    func test_json_family_subtrees_are_plain_objects() throws {
        for file_format in ["json", "jsonc", "toml"] {
            let tree = try new_subtree(file_format)
            XCTAssertTrue(tree.isObject, "Subtree for \(file_format) must be an object")
        }
    }
}

final class ConfigFileFormatParityTests: XCTestCase {
    func test_every_declarable_format_is_implemented() {
        let expected = Set(["json", "jsonc", "toml", "yaml"])
        XCTAssertEqual(Set(CONFIG_FILE_FORMATS), expected)
    }

    func test_every_implemented_format_round_trips_an_empty_document() throws {
        for file_format in CONFIG_FILE_FORMATS {
            let document = try empty_config_document(file_format)
            document["a"] = ["b": 1]
            let rendered = try dump_config_document(document, file_format: file_format)
            let reloaded = try load_config_document(rendered, file_format: file_format)
            XCTAssertEqual(reloaded["a"]?["b"], 1, "Failed for format \(file_format)")
        }
    }
}

final class UnsupportedFormatTests: XCTestCase {
    func test_load_rejects_an_unknown_format() {
        XCTAssertThrowsError(try load_config_document("a = 1", file_format: "ini"))
    }

    func test_dump_rejects_an_unknown_format() {
        let doc = ConfigDocument(fileFormat: "ini")
        XCTAssertThrowsError(try dump_config_document(doc, file_format: "ini"))
    }

    func test_empty_rejects_an_unknown_format() {
        XCTAssertThrowsError(try empty_config_document("ini"))
    }
}
