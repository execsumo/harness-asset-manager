import Foundation

// MARK: - Error

public struct ConfigDocumentError: Error, CustomStringConvertible, Equatable {
    public let message: String
    public init(_ message: String) {
        self.message = message
    }
    public var description: String { message }
}

// MARK: - Comment Blanking

public func blank_jsonc_comments(_ text: String) -> String {
    let characters = Array(text)
    var out = characters
    let length = characters.count
    var commas: [Int] = []
    var index = 0
    var inString = false

    while index < length {
        let char = characters[index]
        if inString {
            if char == "\\" {
                index += 2
                continue
            }
            if char == "\"" {
                inString = false
            }
            index += 1
            continue
        }
        if char == "\"" {
            inString = true
            index += 1
            continue
        }
        if char == "/" && index + 1 < length && characters[index + 1] == "/" {
            while index < length && !characters[index].isNewline {
                out[index] = " "
                index += 1
            }
            continue
        }
        if char == "/" && index + 1 < length && characters[index + 1] == "*" {
            out[index] = " "
            out[index + 1] = " "
            index += 2
            while index + 1 < length && !(characters[index] == "*" && characters[index + 1] == "/") {
                if !characters[index].isNewline {
                    out[index] = " "
                }
                index += 1
            }
            if index + 1 < length {
                out[index] = " "
                out[index + 1] = " "
                index += 2
            } else {
                while index < length {
                    if !characters[index].isNewline {
                        out[index] = " "
                    }
                    index += 1
                }
            }
            continue
        }
        if char == "," {
            commas.append(index)
        }
        index += 1
    }

    let blankedChars = out
    for position in commas {
        var cursor = position + 1
        while cursor < length && blankedChars[cursor].isWhitespace {
            cursor += 1
        }
        if cursor < length && (blankedChars[cursor] == "}" || blankedChars[cursor] == "]") {
            out[position] = " "
        }
    }
    return String(out)
}

// MARK: - Source & Shape

final class Source: @unchecked Sendable {
    let text: String
    let blanked: String
    let textChars: [Character]
    let blankedChars: [Character]

    init(text: String, blanked: String) {
        self.text = text
        self.blanked = blanked
        self.textChars = Array(text)
        self.blankedChars = Array(blanked)
    }

    func isCommentOnly(start: Int, end: Int) -> Bool {
        guard start >= 0, end <= textChars.count, start < end else { return false }
        let blankSlice = String(blankedChars[start..<end]).trimmingCharacters(in: .whitespacesAndNewlines)
        let textSlice = String(textChars[start..<end]).trimmingCharacters(in: .whitespacesAndNewlines)
        return blankSlice.isEmpty && !textSlice.isEmpty
    }

    func slice(_ start: Int, _ end: Int) -> String {
        guard start >= 0, end <= textChars.count, start <= end else { return "" }
        return String(textChars[start..<end])
    }
}

enum ShapeKind: Equatable {
    case object
    case array
    case scalar
}

final class Member: @unchecked Sendable {
    let key: String
    let prefixStart: Int
    let value: Shape

    init(key: String, prefixStart: Int, value: Shape) {
        self.key = key
        self.prefixStart = prefixStart
        self.value = value
    }
}

final class Shape: @unchecked Sendable {
    let start: Int
    var end: Int
    let kind: ShapeKind
    var members: [Member]
    var close: Int
    var memberIndent: String?

    init(start: Int, end: Int, kind: ShapeKind, members: [Member] = [], close: Int = -1, memberIndent: String? = nil) {
        self.start = start
        self.end = end
        self.kind = kind
        self.members = members
        self.close = close
        self.memberIndent = memberIndent
    }
}

final class ShapeScanner {
    private let chars: [Character]
    private let length: Int
    private var index: Int = 0

    init(text: String) {
        self.chars = Array(text)
        self.length = self.chars.count
    }

    func scan() -> Shape {
        skipWhitespace()
        return scanValue()
    }

    private func skipWhitespace() {
        while index < length && chars[index].isWhitespace {
            index += 1
        }
    }

    private func scanValue() -> Shape {
        guard index < length else {
            return Shape(start: index, end: index, kind: .scalar)
        }
        let char = chars[index]
        if char == "{" {
            return scanObject()
        }
        if char == "[" {
            return scanArray()
        }
        return scanScalar()
    }

    private func scanObject() -> Shape {
        let start = index
        index += 1
        var members: [Member] = []
        var close = start
        while true {
            let prefixStart = index
            skipWhitespace()
            if index >= length {
                close = index
                break
            }
            if chars[index] == "}" {
                close = index
                index += 1
                break
            }
            let key = scanStringLiteral()
            skipWhitespace()
            if index < length && chars[index] == ":" {
                index += 1
            }
            skipWhitespace()
            let valShape = scanValue()
            members.append(Member(key: key, prefixStart: prefixStart, value: valShape))
            skipWhitespace()
            if index < length && chars[index] == "," {
                index += 1
                continue
            }
            if index < length && chars[index] == "}" {
                close = index
                index += 1
            }
            break
        }
        let shape = Shape(start: start, end: index, kind: .object, members: members, close: close)
        shape.memberIndent = detectMemberIndent(members: members)
        return shape
    }

    private func scanArray() -> Shape {
        let start = index
        index += 1
        var depth = 1
        while index < length && depth > 0 {
            let char = chars[index]
            if char == "\"" {
                _ = scanStringLiteral()
                continue
            }
            if char == "[" || char == "{" {
                depth += 1
            } else if char == "]" || char == "}" {
                depth -= 1
            }
            index += 1
        }
        return Shape(start: start, end: index, kind: .array)
    }

    private func scanScalar() -> Shape {
        let start = index
        if index < length && chars[index] == "\"" {
            _ = scanStringLiteral()
        } else {
            while index < length && !",}] \t\r\n".contains(chars[index]) {
                index += 1
            }
        }
        return Shape(start: start, end: index, kind: .scalar)
    }

    private func scanStringLiteral() -> String {
        let start = index
        index += 1
        while index < length {
            let char = chars[index]
            if char == "\\" {
                index += 2
                continue
            }
            index += 1
            if char == "\"" {
                break
            }
        }
        let raw = String(chars[start..<index])
        if let data = raw.data(using: .utf8),
           let parsed = try? JSONSerialization.jsonObject(with: data, options: .fragmentsAllowed) as? String {
            return parsed
        }
        return raw.trimmingCharacters(in: CharacterSet(charactersIn: "\""))
    }

    private func detectMemberIndent(members: [Member]) -> String? {
        for member in members {
            let prefix = String(chars[member.prefixStart..<length])
            guard let head = prefix.components(separatedBy: "\"").first else { continue }
            if !head.contains("\n") {
                return nil
            }
            if let lastLine = head.components(separatedBy: "\n").last {
                return lastLine
            }
        }
        return nil
    }
}

// MARK: - JsoncDocument

public final class JsoncDocument: @unchecked Sendable {
    public var value: ConfigValue
    private let text: String
    private let shape: Shape?
    private let source: Source?
    private let original: ConfigValue

    private let hasBOM: Bool

    public init(value: ConfigValue = .object([:])) {
        self.value = value
        self.text = ""
        self.shape = nil
        self.source = nil
        self.original = value
        self.hasBOM = false
    }

    init(
        value: ConfigValue,
        text: String,
        shape: Shape? = nil,
        source: Source? = nil,
        hasBOM: Bool = false
    ) {
        self.value = value
        self.text = text
        self.shape = shape
        self.source = source ?? (text.isEmpty ? nil : Source(text: text, blanked: text))
        self.original = value
        self.hasBOM = hasBOM
    }

    public static func parse(text: String, isJsonc: Bool = true) throws -> JsoncDocument {
        let hasBOM = text.hasPrefix("\u{feff}")
        let cleanText = hasBOM ? String(text.dropFirst()) : text

        let trimmed = cleanText.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return JsoncDocument(value: .object([:]), text: "", shape: nil, source: nil, hasBOM: hasBOM)
        }

        let blanked = isJsonc ? blank_jsonc_comments(cleanText) : cleanText
        guard let data = blanked.data(using: .utf8) else {
            throw ConfigDocumentError("not valid \(isJsonc ? "JSONC" : "JSON"): invalid encoding")
        }

        let jsonObj: Any
        do {
            jsonObj = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
        } catch {
            throw ConfigDocumentError("not valid \(isJsonc ? "JSONC" : "JSON"): \(error.localizedDescription)")
        }

        guard let dict = jsonObj as? [String: Any] else {
            return JsoncDocument(value: ConfigValue(any: jsonObj), text: cleanText, hasBOM: hasBOM)
        }

        let configVal = ConfigValue(any: dict)
        let scanner = ShapeScanner(text: blanked)
        let shape = scanner.scan()
        let source = Source(text: cleanText, blanked: blanked)

        return JsoncDocument(value: configVal, text: cleanText, shape: shape, source: source, hasBOM: hasBOM)
    }

    public func dumps() -> String {
        guard let shape = shape, let source = source, shape.kind == .object else {
            let emitted = emit(value, indent: "") + "\n"
            return hasBOM ? "\u{feff}" + emitted : emitted
        }
        let body = render(new: value, old: original, shape: shape, source: source, indent: "")
        let prefix = source.slice(0, shape.start)
        let suffix = source.slice(shape.end, source.textChars.count)
        let result = prefix + body + suffix
        return hasBOM ? "\u{feff}" + result : result
    }

    // Subscript forwarding to `value`
    public subscript(key: String) -> ConfigValue? {
        get { value[key] }
        set { value[key] = newValue }
    }

    public subscript(path: String...) -> ConfigValue? {
        get {
            var curr: ConfigValue? = value
            for k in path {
                curr = curr?[k]
            }
            return curr
        }
    }
}

// MARK: - Rendering

private func render(new: ConfigValue, old: ConfigValue?, shape: Shape, source: Source, indent: String) -> String {
    if let old = old, new == old {
        return source.slice(shape.start, shape.end)
    }
    guard shape.kind == .object,
          case .object(let newDict) = new,
          let old = old,
          case .object(let oldDict) = old else {
        return emit(new, indent: indent)
    }

    let memberIndent = shape.memberIndent ?? (indent + "  ")
    var parts: [(body: String, trailing: String)] = []
    var lastKept: Member? = nil

    for member in shape.members {
        if newDict[member.key] == nil {
            let rescued = rescuedComment(source: source, member: member)
            if !rescued.isEmpty && !parts.isEmpty {
                let lastIndex = parts.count - 1
                parts[lastIndex] = (parts[lastIndex].body, parts[lastIndex].trailing + rescued)
            }
            continue
        }
        let prefix = source.slice(member.prefixStart, member.value.start)
        let rendered = render(
            new: newDict[member.key]!,
            old: oldDict[member.key],
            shape: member.value,
            source: source,
            indent: memberIndent
        )
        parts.append((prefix + rendered, ""))
        lastKept = member
    }

    let (inline, closing) = trailing(shape: shape, source: source, indent: indent, lastKept: lastKept)
    if !parts.isEmpty && !inline.isEmpty {
        let lastIndex = parts.count - 1
        parts[lastIndex] = (parts[lastIndex].body, parts[lastIndex].trailing + inline)
    }

    let knownKeys = Set(shape.members.map(\.key))
    for (key, val) in newDict where !knownKeys.contains(key) {
        let keyJson = jsonEscape(key)
        parts.append(("\n\(memberIndent)\(keyJson): \(emit(val, indent: memberIndent))", ""))
    }

    if parts.isEmpty {
        return "{}"
    }

    var pieces: [String] = []
    for (index, part) in parts.enumerated() {
        pieces.append(part.body)
        if index < parts.count - 1 {
            pieces.append(",")
        }
        pieces.append(part.trailing)
    }
    return "{" + pieces.joined() + closing
}

private func rescuedComment(source: Source, member: Member) -> String {
    let prefix = source.slice(member.prefixStart, member.value.start)
    guard let newlinePos = prefix.firstIndex(of: "\n") else { return "" }
    let headEnd = member.prefixStart + prefix.distance(from: prefix.startIndex, to: newlinePos)
    if source.isCommentOnly(start: member.prefixStart, end: headEnd) {
        return source.slice(member.prefixStart, headEnd)
    }
    return ""
}

private func trailing(shape: Shape, source: Source, indent: String, lastKept: Member?) -> (String, String) {
    let defaultClosing = "\n\(indent)}"
    if lastKept == nil || shape.members.isEmpty || lastKept !== shape.members.last {
        let within = source.slice(shape.start, shape.close)
        let trailingWhitespaceLen = within.count - within.replacingOccurrences(of: "[ \\t\\r\\n]+$", with: "", options: .regularExpression).count
        let reindent = trailingWhitespaceLen > 0 ? String(within.suffix(trailingWhitespaceLen)) : ""
        return ("", reindent.contains("\n") ? (reindent + "}") : defaultClosing)
    }

    let region = source.slice(lastKept!.value.end, shape.close)
    var modRegion = region
    let leadingSpaces = modRegion.prefix(while: { $0.isWhitespace })
    let afterLeading = modRegion.dropFirst(leadingSpaces.count)
    if afterLeading.starts(with: ",") {
        modRegion = String(afterLeading.dropFirst(1))
    }

    if let newlineIndex = modRegion.firstIndex(of: "\n") {
        let head = String(modRegion[..<newlineIndex])
        let rest = String(modRegion[newlineIndex...])
        let headTrimmed = head.trimmingCharacters(in: .whitespacesAndNewlines)
        return (headTrimmed.isEmpty ? "" : head, rest + "}")
    } else {
        let trimmed = modRegion.trimmingCharacters(in: .whitespacesAndNewlines)
        return ("", trimmed.isEmpty ? defaultClosing : (modRegion + "}"))
    }
}

private func jsonEscape(_ string: String) -> String {
    if let data = try? JSONSerialization.data(withJSONObject: [string]),
       let json = String(data: data, encoding: .utf8) {
        // json is `["string"]` -> extract `"string"`
        if json.hasPrefix("[") && json.hasSuffix("]") {
            let inner = json.dropFirst(1).dropLast(1).trimmingCharacters(in: .whitespaces)
            return inner
        }
    }
    return "\"\(string)\""
}

private func emit(_ value: ConfigValue, indent: String) -> String {
    switch value {
    case .string(let s):
        return jsonEscape(s)
    case .int(let i):
        return "\(i)"
    case .double(let d):
        return "\(d)"
    case .bool(let b):
        return b ? "true" : "false"
    case .null:
        return "null"
    case .array, .object:
        let anyVal = value.toAny()
        if JSONSerialization.isValidJSONObject(anyVal),
           let data = try? JSONSerialization.data(withJSONObject: anyVal, options: [.prettyPrinted, .sortedKeys]),
           let json = String(data: data, encoding: .utf8) {
            if !json.contains("\n") {
                return json
            }
            let lines = json.components(separatedBy: "\n")
            return lines.joined(separator: "\n" + indent)
        }
        return value.description
    }
}
