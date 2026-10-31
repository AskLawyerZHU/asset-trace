// asset-trace SVG→PNG 渲染器（macOS 原生 AppKit，零依赖）
// 由 svg2png.sh 调用：osascript -l JavaScript svg2png.js <in.svg> <out.png> [scale]
// 说明：macOS 11+ 的 NSImage 原生支持 SVG；qlmanage 在部分宿主环境被沙箱策略拦截，故不用。
// JXA 桥接坑：零参数方法（lockFocus/saveGraphicsState 等）不桥接，全程只用带参方法。
ObjC.import('AppKit')

function run(argv) {
  var inPath = argv[0]
  var outPath = argv[1]
  var scale = argv[2] ? parseFloat(argv[2]) : 2

  var src = $.NSImage.alloc.initWithContentsOfFile(inPath)
  if (src.isNil()) return 'FAIL: 无法加载 ' + inPath

  var w = Math.round(src.size.width * scale)
  var h = Math.round(src.size.height * scale)

  var rep = $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
    $(), w, h, 8, 4, true, false, $.NSDeviceRGBColorSpace, 0, 0)
  if (rep.isNil()) return 'FAIL: 无法创建位图'

  var ctx = $.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep)
  $.NSGraphicsContext.setCurrentContext(ctx)
  src.drawInRectFromRectOperationFraction(
    { origin: { x: 0, y: 0 }, size: { width: w, height: h } },
    { origin: { x: 0, y: 0 }, size: { width: src.size.width, height: src.size.height } },
    2, // NSCompositingOperationCopy
    1.0
  )
  $.NSGraphicsContext.setCurrentContext($())

  var png = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $())
  var ok = png.writeToFileAtomically(outPath, true)
  return ok ? 'OK ' + outPath + ' (' + w + 'x' + h + ')' : 'FAIL: 写入失败 ' + outPath
}
