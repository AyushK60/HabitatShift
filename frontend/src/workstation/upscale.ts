/** Display-only image upscaling for the map workspace.
 *
 * The recorded previews are rendered at the native 10 m analysis grid (e.g.
 * Kathmandu is 201 x 225 px), so on a normal screen the browser has to enlarge
 * them 4x or more. The default bilinear filter makes that look smeared.
 *
 * Colour composites (true / false colour) are therefore enlarged here with a
 * Catmull-Rom bicubic kernel, which keeps edges clearly sharper than bilinear.
 * This is presentation only: no new information is created, the recorded PNGs
 * and every analytical raster stay untouched. Data layers (indices, change,
 * masks, counts) are NOT smoothed; the map shows them as crisp native pixels.
 */

const TARGET_LONG_SIDE = 2048;
const MAX_FACTOR = 8;

const cache = new Map<string, Promise<string>>();

function cubicWeights(t: number): [number, number, number, number] {
  // Catmull-Rom (a = -0.5)
  const t2 = t * t;
  const t3 = t2 * t;
  return [
    -0.5 * t3 + t2 - 0.5 * t,
    1.5 * t3 - 2.5 * t2 + 1,
    -1.5 * t3 + 2 * t2 + 0.5 * t,
    0.5 * t3 - 0.5 * t2,
  ];
}

function upscaleBicubic(src: ImageData, factor: number): ImageData {
  const { width: sw, height: sh, data: sd } = src;
  const dw = sw * factor;
  const dh = sh * factor;
  const out = new ImageData(dw, dh);
  const od = out.data;

  // Precompute horizontal taps once per output column.
  const xIdx = new Int32Array(dw * 4);
  const xW = new Float32Array(dw * 4);
  for (let x = 0; x < dw; x++) {
    const fx = (x + 0.5) / factor - 0.5;
    const ix = Math.floor(fx);
    const w = cubicWeights(fx - ix);
    for (let k = 0; k < 4; k++) {
      xIdx[x * 4 + k] = Math.min(sw - 1, Math.max(0, ix - 1 + k));
      xW[x * 4 + k] = w[k];
    }
  }

  for (let y = 0; y < dh; y++) {
    const fy = (y + 0.5) / factor - 0.5;
    const iy = Math.floor(fy);
    const wy = cubicWeights(fy - iy);
    const rows = [0, 1, 2, 3].map(
      (k) => Math.min(sh - 1, Math.max(0, iy - 1 + k)) * sw * 4
    );
    for (let x = 0; x < dw; x++) {
      for (let c = 0; c < 3; c++) {
        let acc = 0;
        for (let j = 0; j < 4; j++) {
          let rowAcc = 0;
          for (let k = 0; k < 4; k++) {
            rowAcc += sd[rows[j] + xIdx[x * 4 + k] * 4 + c] * xW[x * 4 + k];
          }
          acc += rowAcc * wy[j];
        }
        od[(y * dw + x) * 4 + c] = acc < 0 ? 0 : acc > 255 ? 255 : acc;
      }
      od[(y * dw + x) * 4 + 3] = 255;
    }
  }
  return out;
}

/** Returns a blob URL of the bicubic-enlarged image, or the original URL if
 *  anything fails (the map then falls back to the plain image). */
export function smoothUpscaledUrl(url: string): Promise<string> {
  const hit = cache.get(url);
  if (hit) return hit;
  const job = (async () => {
    try {
      const response = await fetch(url);
      if (!response.ok) return url;
      const bitmap = await createImageBitmap(await response.blob());
      const factor = Math.max(
        1,
        Math.min(MAX_FACTOR, Math.round(TARGET_LONG_SIDE / Math.max(bitmap.width, bitmap.height)))
      );
      if (factor === 1) return url;
      const probe = new OffscreenCanvas(bitmap.width, bitmap.height);
      const pctx = probe.getContext("2d");
      if (!pctx) return url;
      pctx.drawImage(bitmap, 0, 0);
      const enlarged = upscaleBicubic(
        pctx.getImageData(0, 0, bitmap.width, bitmap.height),
        factor
      );
      const canvas = new OffscreenCanvas(enlarged.width, enlarged.height);
      const ctx = canvas.getContext("2d");
      if (!ctx) return url;
      ctx.putImageData(enlarged, 0, 0);
      const blob = await canvas.convertToBlob({ type: "image/png" });
      return URL.createObjectURL(blob);
    } catch {
      return url;
    }
  })();
  cache.set(url, job);
  return job;
}
