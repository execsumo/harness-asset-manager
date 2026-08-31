import XCTest
@testable import SwiftConfigDocument

final class PlainJsonRoundTripTests: XCTestCase {
    let FIXTURE = "{\n  \"b\": 2,\n  \"a\": 1\n}\n"

    func test_untouched_document_is_returned_verbatim() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: false)
        XCTAssertEqual(document.dumps(), FIXTURE)
    }

    func test_unowned_keys_survive_a_mutation() throws {
        let document = try JsoncDocument.parse(text: FIXTURE, isJsonc: false)
        document["c"] = 3
        let rendered = document.dumps()
        let reparsed = try JsoncDocument.parse(text: rendered, isJsonc: false)
        XCTAssertEqual(reparsed.value, ["b": 2, "a": 1, "c": 3])
    }

    func test_comment_syntax_is_not_accepted_as_json() {
        XCTAssertThrowsError(try JsoncDocument.parse(text: "{\n // nope\n \"a\": 1\n}", isJsonc: false))
    }
}
