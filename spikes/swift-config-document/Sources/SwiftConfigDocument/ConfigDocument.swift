import Foundation
import TOMLKit
import Yams

public let CONFIG_FILE_FORMATS: [String] = ["json", "jsonc", "toml", "yaml"]

public enum TomlBackend: Sendable {
    case tomlKit
    case surgical
}

public enum YamlBackend: Sendable {
    case yams
    case fallback
}

public final class ConfigDocument: @unchecked Sendable {
    public let fileFormat: String
    public var value: ConfigValue
    
    // Format-specific handlers
    public var jsoncDoc: JsoncDocument?
    public var tomlKitDoc: TomlKitDocument?
    public var tomlSurgicalDoc: TomlSurgicalDocument?
    public var yamsDoc: YamsDocument?

    public var tomlBackend: TomlBackend = .tomlKit
    public var yamlBackend: YamlBackend = .yams

    public init(fileFormat: String, value: ConfigValue = .object([:])) {
        self.fileFormat = fileFormat
        self.value = value
    }

    public subscript(key: String) -> ConfigValue? {
        get {
            syncFromUnderlying()
            return value[key]
        }
        set {
            value[key] = newValue
            syncToUnderlying()
        }
    }

    public subscript(path: String...) -> ConfigValue? {
        get {
            syncFromUnderlying()
            var curr: ConfigValue? = value
            for k in path {
                curr = curr?[k]
            }
            return curr
        }
    }

    private func syncFromUnderlying() {
        if let j = jsoncDoc {
            self.value = j.value
        } else if let ts = tomlSurgicalDoc {
            self.value = ts.value
        }
    }

    private func syncToUnderlying() {
        if let j = jsoncDoc {
            j.value = self.value
        }
        if let ts = tomlSurgicalDoc {
            ts.value = self.value
        }
    }
}

// MARK: - Public API

public func load_config_document(_ text: String, file_format: String, tomlBackend: TomlBackend = .tomlKit) throws -> ConfigDocument {
    let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
    guard CONFIG_FILE_FORMATS.contains(file_format) else {
        throw ConfigDocumentError("unsupported config file format: \(file_format)")
    }

    if trimmed.isEmpty {
        return try empty_config_document(file_format)
    }

    switch file_format {
    case "json":
        let jdoc = try JsoncDocument.parse(text: text, isJsonc: false)
        let doc = ConfigDocument(fileFormat: file_format, value: jdoc.value)
        doc.jsoncDoc = jdoc
        return doc

    case "jsonc":
        let jdoc = try JsoncDocument.parse(text: text, isJsonc: true)
        let doc = ConfigDocument(fileFormat: file_format, value: jdoc.value)
        doc.jsoncDoc = jdoc
        return doc

    case "toml":
        let doc = ConfigDocument(fileFormat: file_format)
        doc.tomlBackend = tomlBackend
        if tomlBackend == .surgical {
            let tsDoc = try TomlSurgicalDocument.parse(text: text)
            doc.value = tsDoc.value
            doc.tomlSurgicalDoc = tsDoc
        } else {
            let tkDoc = try TomlKitDocument.parse(text: text)
            doc.value = tomlTableToConfigValue(tkDoc.table)
            doc.tomlKitDoc = tkDoc
        }
        return doc

    case "yaml":
        let ydoc = try YamsDocument.parse(text: text)
        let doc = ConfigDocument(fileFormat: file_format)
        if let node = ydoc.node {
            doc.value = yamlNodeToConfigValue(node)
        } else {
            doc.value = .object([:])
        }
        doc.yamsDoc = ydoc
        return doc

    default:
        throw ConfigDocumentError("unsupported config file format: \(file_format)")
    }
}

public func dump_config_document(_ document: ConfigDocument, file_format: String) throws -> String {
    guard CONFIG_FILE_FORMATS.contains(file_format) else {
        throw ConfigDocumentError("unsupported config file format: \(file_format)")
    }

    switch file_format {
    case "json", "jsonc":
        if let jdoc = document.jsoncDoc {
            jdoc.value = document.value
            return jdoc.dumps()
        }
        let jdoc = JsoncDocument(value: document.value)
        return jdoc.dumps()

    case "toml":
        if document.tomlBackend == .surgical {
            if let tsDoc = document.tomlSurgicalDoc {
                tsDoc.value = document.value
                return tsDoc.dumps()
            }
            let tsDoc = TomlSurgicalDocument(value: document.value)
            return tsDoc.dumps()
        } else {
            if let tkDoc = document.tomlKitDoc {
                // Replay changes from document.value onto tkDoc.table
                applyChangesToTomlTable(tkDoc.table, new: document.value)
                return tkDoc.dumps()
            }
            let table = configValueToTomlTable(document.value)
            return table.convert()
        }

    case "yaml":
        if let ydoc = document.yamsDoc {
            // Update node from document.value
            ydoc.node = configValueToYamlNode(document.value)
            return try ydoc.dumps()
        }
        let node = configValueToYamlNode(document.value)
        return try Yams.serialize(node: node)

    default:
        throw ConfigDocumentError("unsupported config file format: \(file_format)")
    }
}

public func empty_config_document(_ file_format: String) throws -> ConfigDocument {
    guard CONFIG_FILE_FORMATS.contains(file_format) else {
        throw ConfigDocumentError("unsupported config file format: \(file_format)")
    }
    return ConfigDocument(fileFormat: file_format, value: .object([:]))
}

public func new_subtree(_ file_format: String) throws -> ConfigValue {
    guard CONFIG_FILE_FORMATS.contains(file_format) else {
        throw ConfigDocumentError("unsupported config file format: \(file_format)")
    }
    return .object([:])
}

// MARK: - TOML Helper Functions

private func tomlTableToConfigValue(_ table: TOMLTable) -> ConfigValue {
    var dict: [String: ConfigValue] = [:]
    for (k, v) in table {
        dict[k] = tomlValueToConfigValue(v.tomlValue)
    }
    return .object(dict)
}

private func tomlValueToConfigValue(_ val: TOMLValue) -> ConfigValue {
    switch val.type {
    case .string: return .string(val.string ?? "")
    case .int: return .int(val.int ?? 0)
    case .double: return .double(val.double ?? 0.0)
    case .bool: return .bool(val.bool ?? false)
    case .table:
        return val.table != nil ? tomlTableToConfigValue(val.table!) : .object([:])
    case .array:
        return val.array != nil ? .array(val.array!.map { tomlValueToConfigValue($0.tomlValue) }) : .array([])
    default:
        if let s = val.string { return .string(s) }
        return .null
    }
}

private func configValueToTomlTable(_ val: ConfigValue) -> TOMLTable {
    let table = TOMLTable()
    guard case .object(let dict) = val else { return table }
    for (k, v) in dict {
        table[k] = configValueToTomlValueConvertible(v)
    }
    return table
}

private func configValueToTomlValueConvertible(_ val: ConfigValue) -> TOMLValueConvertible {
    switch val {
    case .string(let s): return s
    case .int(let i): return i
    case .double(let d): return d
    case .bool(let b): return b
    case .null: return ""
    case .array(let a):
        return TOMLArray(a.map { configValueToTomlValueConvertible($0) })
    case .object(let o):
        let tbl = TOMLTable()
        for (k, v) in o {
            tbl[k] = configValueToTomlValueConvertible(v)
        }
        return tbl
    }
}

private func applyChangesToTomlTable(_ target: TOMLTable, new: ConfigValue) {
    guard case .object(let newDict) = new else { return }
    let existingKeys = target.keys
    for k in existingKeys where newDict[k] == nil {
        target[k] = nil
    }
    for (k, v) in newDict {
        if case .object = v, let subTable = target[k]?.table {
            applyChangesToTomlTable(subTable, new: v)
        } else {
            target[k] = configValueToTomlValueConvertible(v)
        }
    }
}

// MARK: - YAML Helper Functions

private func yamlNodeToConfigValue(_ node: Node) -> ConfigValue {
    switch node {
    case .scalar(let s):
        if let b = Bool(s.string) { return .bool(b) }
        if let i = Int(s.string) { return .int(i) }
        if let d = Double(s.string) { return .double(d) }
        if s.string == "null" || s.string == "~" { return .null }
        return .string(s.string)
    case .sequence(let seq):
        return .array(seq.map { yamlNodeToConfigValue($0) })
    case .mapping(let map):
        var dict: [String: ConfigValue] = [:]
        for (k, v) in map {
            dict[k.string ?? ""] = yamlNodeToConfigValue(v)
        }
        return .object(dict)
    case .alias(let a):
        return .string(a.anchor.rawValue)
    }
}

private func configValueToYamlNode(_ val: ConfigValue) -> Node {
    switch val {
    case .string(let s): return Node.scalar(Node.Scalar(s))
    case .int(let i): return Node.scalar(Node.Scalar("\(i)"))
    case .double(let d): return Node.scalar(Node.Scalar("\(d)"))
    case .bool(let b): return Node.scalar(Node.Scalar(b ? "true" : "false"))
    case .null: return Node.scalar(Node.Scalar("null"))
    case .array(let arr):
        return Node.sequence(Node.Sequence(arr.map { configValueToYamlNode($0) }))
    case .object(let dict):
        let pairs: [(Node, Node)] = dict.map { (Node.scalar(Node.Scalar($0.key)), configValueToYamlNode($0.value)) }
        return Node.mapping(Node.Mapping(pairs))
    }
}
