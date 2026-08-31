// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SwiftConfigDocument",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .library(name: "SwiftConfigDocument", targets: ["SwiftConfigDocument"]),
    ],
    dependencies: [
        .package(url: "https://github.com/LebJe/TOMLKit.git", from: "0.6.0"),
        .package(url: "https://github.com/jpsim/Yams.git", from: "5.4.0"),
    ],
    targets: [
        .target(
            name: "SwiftConfigDocument",
            dependencies: [
                .product(name: "TOMLKit", package: "TOMLKit"),
                .product(name: "Yams", package: "Yams"),
            ]
        ),
        .executableTarget(
            name: "SwiftConfigDocumentDiffCLI",
            dependencies: [
                "SwiftConfigDocument",
                .product(name: "TOMLKit", package: "TOMLKit"),
                .product(name: "Yams", package: "Yams"),
            ]
        ),
        .testTarget(
            name: "SwiftConfigDocumentTests",
            dependencies: [
                "SwiftConfigDocument",
                .product(name: "TOMLKit", package: "TOMLKit"),
                .product(name: "Yams", package: "Yams"),
            ]
        ),
    ]
)
