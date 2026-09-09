import AppKit
import CoreGraphics
import Foundation
import Vision

struct OCRLine: Codable {
    let text: String
    let confidence: Float
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct FrameRecord: Codable {
    let recording: String
    let frame: String
    let time_sec: Double
    let dhash: String
    let text: String
    let lines: [OCRLine]
    let error_terms: [String]
}

func differenceHash(_ image: CGImage) -> String {
    let width = 9
    let height = 8
    var pixels = [UInt8](repeating: 0, count: width * height)
    let context = CGContext(data: &pixels, width: width, height: height, bitsPerComponent: 8,
                            bytesPerRow: width, space: CGColorSpaceCreateDeviceGray(),
                            bitmapInfo: CGImageAlphaInfo.none.rawValue)!
    context.interpolationQuality = .low
    context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
    var hash: UInt64 = 0
    var bit: UInt64 = 1
    for row in 0..<height {
        for column in 0..<(width - 1) {
            if pixels[row * width + column] > pixels[row * width + column + 1] { hash |= bit }
            bit <<= 1
        }
    }
    return String(format: "%016llx", hash)
}

func imageFromFile(_ url: URL) -> CGImage? {
    guard let image = NSImage(contentsOf: url) else { return nil }
    var rect = CGRect(origin: .zero, size: image.size)
    return image.cgImage(forProposedRect: &rect, context: nil, hints: nil)
}

guard CommandLine.arguments.count == 5 else {
    fputs("Usage: vision_ocr <frames_dir> <recording_label> <output_jsonl> <fast|accurate>\n", stderr)
    exit(2)
}

let framesDirectory = URL(fileURLWithPath: CommandLine.arguments[1])
let recording = CommandLine.arguments[2]
let outputURL = URL(fileURLWithPath: CommandLine.arguments[3])
let mode = CommandLine.arguments[4]
let files = try FileManager.default.contentsOfDirectory(at: framesDirectory,
    includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])
    .filter { $0.pathExtension.lowercased() == "jpg" }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

FileManager.default.createFile(atPath: outputURL.path, contents: nil)
let outputHandle = try FileHandle(forWritingTo: outputURL)
defer { try? outputHandle.close() }
let encoder = JSONEncoder()
let errorPatterns = ["error", "failed", "warning", "invalid", "unable to", "try again", "something went wrong", "403", "404", "500"]

for (offset, fileURL) in files.enumerated() {
    autoreleasepool {
        guard let image = imageFromFile(fileURL) else { return }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = mode == "accurate" ? .accurate : .fast
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["en-US"]
        request.minimumTextHeight = 0.006
        do {
            try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
            let observations = (request.results ?? []).sorted {
                if abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.015 {
                    return $0.boundingBox.midY > $1.boundingBox.midY
                }
                return $0.boundingBox.minX < $1.boundingBox.minX
            }
            let lines: [OCRLine] = observations.compactMap { observation in
                guard let candidate = observation.topCandidates(1).first else { return nil }
                let box = observation.boundingBox
                return OCRLine(text: candidate.string, confidence: candidate.confidence,
                    x: box.minX, y: box.minY, width: box.width, height: box.height)
            }
            let joined = lines.map(\.text).joined(separator: " \n")
            let lower = joined.lowercased()
            let errors = errorPatterns.filter { lower.contains($0) }
            let digits = fileURL.deletingPathExtension().lastPathComponent.split(separator: "_").last ?? "1"
            let frameNumber = Int(digits) ?? (offset + 1)
            let record = FrameRecord(recording: recording, frame: fileURL.lastPathComponent,
                time_sec: Double(max(0, frameNumber - 1)), dhash: differenceHash(image),
                text: joined, lines: lines, error_terms: errors)
            outputHandle.write(try encoder.encode(record))
            outputHandle.write(Data([0x0A]))
        } catch {
            fputs("OCR failed for \(fileURL.path): \(error)\n", stderr)
        }
    }
    if (offset + 1) % 100 == 0 || offset + 1 == files.count {
        print("screen text: \(offset + 1)/\(files.count)")
        fflush(stdout)
    }
}
