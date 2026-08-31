import Foundation
import SwiftConfigDocument

func logError(_ msg: String) {
    if let data = (msg + "\n").data(using: .utf8) {
        FileHandle.standardError.write(data)
    }
}

func run() {
    let args = CommandLine.arguments
    var format = "jsonc"
    var backend = "default"
    var mutation = "none"
    var filePath: String? = nil

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--format":
            if i + 1 < args.count { format = args[i + 1]; i += 1 }
        case "--backend":
            if i + 1 < args.count { backend = args[i + 1]; i += 1 }
        case "--mutation":
            if i + 1 < args.count { mutation = args[i + 1]; i += 1 }
        case "--file":
            if i + 1 < args.count { filePath = args[i + 1]; i += 1 }
        default:
            break
        }
        i += 1
    }

    let inputData: Data
    if let path = filePath {
        guard let data = FileManager.default.contents(atPath: path) else {
            logError("Error: cannot read file at \(path)")
            exit(1)
        }
        inputData = data
    } else {
        inputData = FileHandle.standardInput.readDataToEndOfFile()
    }

    guard let text = String(data: inputData, encoding: .utf8) else {
        logError("Error: invalid UTF-8 input")
        exit(1)
    }

    let tomlBackend: TomlBackend = (backend == "surgical") ? .surgical : .tomlKit

    do {
        let doc = try load_config_document(text, file_format: format, tomlBackend: tomlBackend)

        switch mutation {
        case "none":
            break
        case "add_mcp":
            if format == "toml" {
                var mcp = doc["mcp_servers"]?.object ?? [:]
                mcp["context7"] = ["command": "npx", "args": ["-y", "c7"]]
                doc["mcp_servers"] = .object(mcp)
            } else if format == "yaml" {
                var mcp = doc["mcp_servers"]?.object ?? [:]
                mcp["context7"] = ["command": "npx"]
                doc["mcp_servers"] = .object(mcp)
            } else {
                var mcp = doc["mcp"]?.object ?? [:]
                mcp["context7"] = ["type": "local", "command": ["npx", "c7"]]
                doc["mcp"] = .object(mcp)
            }
        case "remove_mcp":
            if format == "toml" || format == "yaml" {
                var mcp = doc["mcp_servers"]?.object ?? [:]
                mcp.removeValue(forKey: "exa")
                doc["mcp_servers"] = .object(mcp)
            } else {
                var mcp = doc["mcp"]?.object ?? [:]
                mcp.removeValue(forKey: "exa")
                doc["mcp"] = .object(mcp)
            }
        case "edit_scalar":
            if format == "toml" {
                doc["model"] = "gpt-5-codex"
            } else if format == "yaml" {
                doc["model"] = "claude-3-7-sonnet-latest"
            } else {
                doc["theme"] = "system"
            }
        default:
            break
        }

        let output = try dump_config_document(doc, file_format: format)
        print(output, terminator: "")
    } catch {
        logError("Error: \(error)")
        exit(1)
    }
}

run()
