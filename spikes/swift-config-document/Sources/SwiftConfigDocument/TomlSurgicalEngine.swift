import Foundation
import TOMLKit

/// A source-preserving TOML document that keeps original text and surgically splices modifications.
public final class TomlSurgicalDocument: @unchecked Sendable {
    public var value: ConfigValue
    private let text: String
    private let originalValue: ConfigValue
    private let hasBOM: Bool

    public init(value: ConfigValue = .object([:]), text: String = "", hasBOM: Bool = false) {
        self.value = value
        self.text = text
        self.originalValue = value
        self.hasBOM = hasBOM
    }

    public static func parse(text: String) throws -> TomlSurgicalDocument {
        let hasBOM = text.hasPrefix("\u{feff}")
        let cleanText = hasBOM ? String(text.dropFirst()) : text

        let trimmed = cleanText.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return TomlSurgicalDocument(hasBOM: hasBOM)
        }

        do {
            let table = try TOMLTable(string: cleanText)
            let configVal = tomlTableToConfigValue(table)
            return TomlSurgicalDocument(value: configVal, text: cleanText, hasBOM: hasBOM)
        } catch let err as TOMLParseError {
            throw ConfigDocumentError("not valid TOML: \(err)")
        } catch {
            throw ConfigDocumentError("not valid TOML: \(error)")
        }
    }

    public func dumps() -> String {
        let res: String
        if text.isEmpty {
            res = emitTomlValue(value, section: nil)
        } else if value == originalValue {
            res = text
        } else {
            res = renderTomlChanges(originalText: text, new: value, old: originalValue)
        }
        return hasBOM ? "\u{feff}" + res : res
    }

    public subscript(key: String) -> ConfigValue? {
        get { value[key] }
        set { value[key] = newValue }
    }
}

// MARK: - TOML Conversion Helpers

private func tomlTableToConfigValue(_ table: TOMLTable) -> ConfigValue {
    var dict: [String: ConfigValue] = [:]
    for (k, v) in table {
        dict[k] = tomlValueToConfigValue(v.tomlValue)
    }
    return .object(dict)
}

private func tomlValueToConfigValue(_ val: TOMLValue) -> ConfigValue {
    switch val.type {
    case .string:
        return .string(val.string ?? "")
    case .int:
        return .int(val.int ?? 0)
    case .double:
        return .double(val.double ?? 0.0)
    case .bool:
        return .bool(val.bool ?? false)
    case .table:
        if let t = val.table {
            return tomlTableToConfigValue(t)
        }
        return .object([:])
    case .array:
        if let a = val.array {
            return .array(a.map { tomlValueToConfigValue($0.tomlValue) })
        }
        return .array([])
    default:
        if let s = val.string { return .string(s) }
        return .null
    }
}

// MARK: - Surgical Rendering

struct TomlSection {
    let name: String? // nil for root section
    let headerLine: String?
    let startIndex: Int
    var endIndex: Int
    var lines: [String]
}

private func renderTomlChanges(originalText: String, new: ConfigValue, old: ConfigValue) -> String {
    guard case .object(let newDict) = new, case .object(let oldDict) = old else {
        return emitTomlValue(new, section: nil)
    }

    // Split document into lines and discover table sections
    let rawLines = originalText.components(separatedBy: "\n")
    var sections: [TomlSection] = []
    var currentName: String? = nil
    var currentHeader: String? = nil
    var currentStart = 0
    var currentLines: [String] = []

    for (lineIdx, line) in rawLines.enumerated() {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        if trimmed.hasPrefix("[") && trimmed.hasSuffix("]") && !trimmed.hasPrefix("[[") {
            let headerContent = String(trimmed.dropFirst(1).dropLast(1)).trimmingCharacters(in: .whitespaces)
            if !sections.isEmpty || !currentLines.isEmpty || currentName != nil {
                sections.append(TomlSection(name: currentName, headerLine: currentHeader, startIndex: currentStart, endIndex: lineIdx, lines: currentLines))
            }
            currentName = headerContent
            currentHeader = line
            currentStart = lineIdx
            currentLines = [line]
        } else {
            currentLines.append(line)
        }
    }
    sections.append(TomlSection(name: currentName, headerLine: currentHeader, startIndex: currentStart, endIndex: rawLines.count, lines: currentLines))

    // Track handled keys
    var outputSections: [String] = []

    // 1. Process root section
    if let rootSec = sections.first(where: { $0.name == nil }) {
        var rootLines = rootSec.lines
        for (k, v) in newDict {
            if !v.isObject { // Root key-value pair
                let oldVal = oldDict[k]
                if oldVal == nil {
                    // Added root key
                    rootLines.append("\(k) = \(emitTomlInline(v))")
                } else if oldVal != v {
                    // Modified root key - find and replace line
                    var found = false
                    for (i, line) in rootLines.enumerated() {
                        let trimmed = line.trimmingCharacters(in: .whitespaces)
                        if trimmed.hasPrefix("\(k) ") || trimmed.hasPrefix("\(k)=") || trimmed.hasPrefix("\(k)\t") {
                            // Extract comment if present
                            let comment = extractTrailingComment(line)
                            rootLines[i] = "\(k) = \(emitTomlInline(v))\(comment)"
                            found = true
                            break
                        }
                    }
                    if !found {
                        rootLines.append("\(k) = \(emitTomlInline(v))")
                    }
                }
            }
        }
        // Check for deleted root keys
        for (k, _) in oldDict where newDict[k] == nil {
            rootLines.removeAll { line in
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                return trimmed.hasPrefix("\(k) ") || trimmed.hasPrefix("\(k)=") || trimmed.hasPrefix("\(k)\t")
            }
        }
        outputSections.append(rootLines.joined(separator: "\n"))
    }

    // 2. Process table sections
    for sec in sections where sec.name != nil {
        guard let name = sec.name else { continue }
        let keyPath = name.components(separatedBy: ".")
        
        // Check if table is deleted
        if isKeyPathDeleted(keyPath: keyPath, in: newDict) {
            // Drop this section entirely
            continue
        }

        let newTableVal = getValueAtPath(keyPath: keyPath, in: newDict)
        let oldTableVal = getValueAtPath(keyPath: keyPath, in: oldDict)

        if let newTableVal = newTableVal, newTableVal == oldTableVal {
            // Untouched section: preserve completely verbatim
            outputSections.append(sec.lines.joined(separator: "\n"))
        } else if let newTableVal = newTableVal, case .object(let newSub) = newTableVal {
            // Modified section
            var secLines = sec.lines
            let oldSub = (oldTableVal?.object) ?? [:]
            
            // Apply key edits inside section
            for (k, v) in newSub {
                if !v.isObject {
                    let oldV = oldSub[k]
                    if oldV == nil {
                        secLines.append("\(k) = \(emitTomlInline(v))")
                    } else if oldV != v {
                        for (i, line) in secLines.enumerated() {
                            let trimmed = line.trimmingCharacters(in: .whitespaces)
                            if trimmed.hasPrefix("\(k) ") || trimmed.hasPrefix("\(k)=") || trimmed.hasPrefix("\(k)\t") {
                                let comment = extractTrailingComment(line)
                                secLines[i] = "\(k) = \(emitTomlInline(v))\(comment)"
                                break
                            }
                        }
                    }
                }
            }
            for (k, _) in oldSub where newSub[k] == nil {
                secLines.removeAll { line in
                    let trimmed = line.trimmingCharacters(in: .whitespaces)
                    return trimmed.hasPrefix("\(k) ") || trimmed.hasPrefix("\(k)=") || trimmed.hasPrefix("\(k)\t")
                }
            }
            outputSections.append(secLines.joined(separator: "\n"))
        }
    }

    // 3. Handle newly added tables
    for (topKey, topVal) in newDict {
        if case .object(let topObj) = topVal {
            for (subKey, subVal) in topObj {
                let fullPath = "\(topKey).\(subKey)"
                if !sections.contains(where: { $0.name == fullPath }) {
                    if let oldTop = oldDict[topKey]?.object, oldTop[subKey] != nil {
                        continue
                    }
                    // Newly added table
                    var newSecLines: [String] = ["\n[\(fullPath)]"]
                    if case .object(let subDict) = subVal {
                        for (k, v) in subDict {
                            newSecLines.append("\(k) = \(emitTomlInline(v))")
                        }
                    }
                    outputSections.append(newSecLines.joined(separator: "\n"))
                }
            }
        }
    }

    let joined = outputSections.joined(separator: "\n")
    // Normalize consecutive newlines
    return joined.hasSuffix("\n") ? joined : joined + "\n"
}

private func extractTrailingComment(_ line: String) -> String {
    guard let hashIdx = line.firstIndex(of: "#") else { return "" }
    return "  " + String(line[hashIdx...])
}

private func isKeyPathDeleted(keyPath: [String], in dict: [String: ConfigValue]) -> Bool {
    var curr: ConfigValue? = .object(dict)
    for k in keyPath {
        guard let obj = curr?.object, let next = obj[k] else { return true }
        curr = next
    }
    return false
}

private func getValueAtPath(keyPath: [String], in dict: [String: ConfigValue]) -> ConfigValue? {
    var curr: ConfigValue? = .object(dict)
    for k in keyPath {
        guard let obj = curr?.object, let next = obj[k] else { return nil }
        curr = next
    }
    return curr
}

private func emitTomlInline(_ val: ConfigValue) -> String {
    switch val {
    case .string(let s):
        return "\"\(s)\""
    case .int(let i):
        return "\(i)"
    case .double(let d):
        return "\(d)"
    case .bool(let b):
        return b ? "true" : "false"
    case .null:
        return "\"\""
    case .array(let a):
        return "[\(a.map { emitTomlInline($0) }.joined(separator: ", "))]"
    case .object(let o):
        let pairs = o.map { "\($0.key) = \(emitTomlInline($0.value))" }.joined(separator: ", ")
        return "{ \(pairs) }"
    }
}

private func emitTomlValue(_ val: ConfigValue, section: String?) -> String {
    guard case .object(let dict) = val else { return "" }
    var lines: [String] = []
    if let section = section {
        lines.append("[\(section)]")
    }
    var subTables: [(String, ConfigValue)] = []
    for (k, v) in dict {
        if case .object = v {
            let nextSection = section != nil ? "\(section!).\(k)" : k
            subTables.append((nextSection, v))
        } else {
            lines.append("\(k) = \(emitTomlInline(v))")
        }
    }
    var out = lines.joined(separator: "\n")
    for (subSec, subVal) in subTables {
        out += "\n\n" + emitTomlValue(subVal, section: subSec)
    }
    return out.hasSuffix("\n") ? out : out + "\n"
}
