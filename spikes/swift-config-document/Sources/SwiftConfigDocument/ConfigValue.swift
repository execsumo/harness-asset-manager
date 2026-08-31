import Foundation
#if canImport(CoreFoundation)
import CoreFoundation
#endif

/// A dynamically typed value representing JSON, JSONC, TOML, or YAML structures.
public enum ConfigValue: Equatable, Sendable, CustomStringConvertible {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case null
    case array([ConfigValue])
    case object([String: ConfigValue])

    public var description: String {
        switch self {
        case .string(let s): return "\"\(s)\""
        case .int(let i): return "\(i)"
        case .double(let d): return "\(d)"
        case .bool(let b): return "\(b)"
        case .null: return "null"
        case .array(let a): return "[\(a.map(\.description).joined(separator: ", "))]"
        case .object(let o):
            let pairs = o.map { "\"\($0.key)\": \($0.value.description)" }.joined(separator: ", ")
            return "{\(pairs)}"
        }
    }

    // MARK: - Accessors

    public var string: String? {
        if case .string(let s) = self { return s }
        return nil
    }

    public var int: Int? {
        if case .int(let i) = self { return i }
        return nil
    }

    public var double: Double? {
        switch self {
        case .double(let d): return d
        case .int(let i): return Double(i)
        default: return nil
        }
    }

    public var bool: Bool? {
        if case .bool(let b) = self { return b }
        return nil
    }

    public var isNull: Bool {
        if case .null = self { return true }
        return false
    }

    public var array: [ConfigValue]? {
        get {
            if case .array(let a) = self { return a }
            return nil
        }
        set {
            if let newValue = newValue {
                self = .array(newValue)
            }
        }
    }

    public var object: [String: ConfigValue]? {
        get {
            if case .object(let o) = self { return o }
            return nil
        }
        set {
            if let newValue = newValue {
                self = .object(newValue)
            }
        }
    }

    public var isObject: Bool {
        if case .object = self { return true }
        return false
    }

    public var isArray: Bool {
        if case .array = self { return true }
        return false
    }

    // MARK: - Subscripts

    public subscript(key: String) -> ConfigValue? {
        get {
            guard case .object(let dict) = self else { return nil }
            return dict[key]
        }
        set {
            guard case .object(var dict) = self else { return }
            if let newValue = newValue {
                dict[key] = newValue
            } else {
                dict.removeValue(forKey: key)
            }
            self = .object(dict)
        }
    }

    public subscript(index: Int) -> ConfigValue? {
        get {
            guard case .array(let arr) = self, index >= 0, index < arr.count else { return nil }
            return arr[index]
        }
        set {
            guard case .array(var arr) = self, index >= 0, index < arr.count else { return }
            if let newValue = newValue {
                arr[index] = newValue
            } else {
                arr.remove(at: index)
            }
            self = .array(arr)
        }
    }

    public subscript(path: String...) -> ConfigValue? {
        get {
            var current: ConfigValue = self
            for key in path {
                guard let next = current[key] else { return nil }
                current = next
            }
            return current
        }
    }

    // MARK: - Conversion to/from Any / JSONSerialization

    public init(any: Any) {
        switch any {
        case let val as ConfigValue:
            self = val
        case let s as String:
            self = .string(s)
        case let arr as [Any]:
            self = .array(arr.map { ConfigValue(any: $0) })
        case let dict as [String: Any]:
            var obj: [String: ConfigValue] = [:]
            for (k, v) in dict {
                obj[k] = ConfigValue(any: v)
            }
            self = .object(obj)
        case let dict as [AnyHashable: Any]:
            var obj: [String: ConfigValue] = [:]
            for (k, v) in dict {
                obj[String(describing: k)] = ConfigValue(any: v)
            }
            self = .object(obj)
        case is NSNull:
            self = .null
        case let num as NSNumber:
            #if canImport(Darwin)
            if CFGetTypeID(num as CFTypeRef) == CFBooleanGetTypeID() {
                self = .bool(num.boolValue)
            } else if String(cString: num.objCType) == "d" || String(cString: num.objCType) == "f" {
                self = .double(num.doubleValue)
            } else {
                self = .int(num.intValue)
            }
            #else
            // On Linux Foundation, check CFBoolean or type of the underlying instance
            if CFGetTypeID(num as CFTypeRef) == CFBooleanGetTypeID() {
                self = .bool(num.boolValue)
            } else if "\(type(of: any))" == "__NSCFBoolean" || "\(type(of: any))" == "Bool" {
                self = .bool(num.boolValue)
            } else if floor(num.doubleValue) != num.doubleValue {
                self = .double(num.doubleValue)
            } else {
                self = .int(num.intValue)
            }
            #endif
        default:
            self = .null
        }
    }

    public func toAny() -> Any {
        switch self {
        case .string(let s): return s
        case .int(let i): return i
        case .double(let d): return d
        case .bool(let b): return b
        case .null: return NSNull()
        case .array(let a): return a.map { $0.toAny() }
        case .object(let o):
            var dict: [String: Any] = [:]
            for (k, v) in o {
                dict[k] = v.toAny()
            }
            return dict
        }
    }
}

// MARK: - ExpressibleBy Literals

extension ConfigValue: ExpressibleByStringLiteral {
    public init(stringLiteral value: String) {
        self = .string(value)
    }
}

extension ConfigValue: ExpressibleByIntegerLiteral {
    public init(integerLiteral value: Int) {
        self = .int(value)
    }
}

extension ConfigValue: ExpressibleByFloatLiteral {
    public init(floatLiteral value: Double) {
        self = .double(value)
    }
}

extension ConfigValue: ExpressibleByBooleanLiteral {
    public init(booleanLiteral value: Bool) {
        self = .bool(value)
    }
}

extension ConfigValue: ExpressibleByNilLiteral {
    public init(nilLiteral: ()) {
        self = .null
    }
}

extension ConfigValue: ExpressibleByArrayLiteral {
    public init(arrayLiteral elements: ConfigValue...) {
        self = .array(elements)
    }
}

extension ConfigValue: ExpressibleByDictionaryLiteral {
    public init(dictionaryLiteral elements: (String, ConfigValue)...) {
        var dict: [String: ConfigValue] = [:]
        for (k, v) in elements {
            dict[k] = v
        }
        self = .object(dict)
    }
}
