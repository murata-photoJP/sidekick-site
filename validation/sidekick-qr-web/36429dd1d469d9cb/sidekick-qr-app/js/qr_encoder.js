// Sidekick QR encoder —— browser 内で文字列を standard QR（Model 2）の module 行列にし、PNG にする（HD-PLANNERSHAREV2-GIC-001、AI-15963）。
//
// Generic Image Card の QR を **server へ URL を送らずに**作るための、依存なしの最小実装。
// 方式は ISO/IEC 18004 の標準手順どおり: byte mode（UTF-8）→ 最小 version → Reed–Solomon（GF(256), 0x11D）→ block interleave →
// function pattern（finder / timing / alignment / format / version）→ 8 mask の penalty 最小を選ぶ（評価は segno と同じ数え方）。
//
// 品質の基準は Planner（`qr_share_render.py`、segno 1.6.6）と同じ:
//   * ECC は既定 **M**、**勝手に上げない**（segno の `boost_error=False` と同じ）
//   * quiet zone **4 module**、1 module = **整数 px**（既定 10）、canvas へは module ごとに塗るだけで**補間しない**
//   * 容量は byte mode / ECC M / version 40 の 2,331 B まで（超えたら QR_CAPACITY_EXCEEDED）
// segno との一致は test（`test_generic_qr_encoder_browser`）で module 行列を直接比べて確かめる。
//
// 外部 resource を読まない。ネットワークに触れない。
"use strict";

(function (root) {
  const ECC = Object.freeze({ L: 0, M: 1, Q: 2, H: 3 });
  const ECC_FORMAT_BITS = [1, 0, 3, 2];

  // [ecc][version]（index 0 は未使用）
  const ECC_CODEWORDS_PER_BLOCK = [
    [-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
    [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28],
    [-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
    [-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
  ];
  const NUM_ERROR_CORRECTION_BLOCKS = [
    [-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25],
    [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49],
    [-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68],
    [-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81],
  ];

  class QrError extends Error {
    constructor(code, message) {
      super(message);
      this.code = code;
    }
  }

  const bit = (value, index) => ((value >>> index) & 1) !== 0;

  function rawDataModules(version) {
    let result = (16 * version + 128) * version + 64;
    if (version >= 2) {
      const align = Math.floor(version / 7) + 2;
      result -= (25 * align - 10) * align - 55;
      if (version >= 7) result -= 36;
    }
    return result;
  }

  function dataCodewords(version, ecc) {
    return Math.floor(rawDataModules(version) / 8)
      - ECC_CODEWORDS_PER_BLOCK[ecc][version] * NUM_ERROR_CORRECTION_BLOCKS[ecc][version];
  }

  // ---- Reed–Solomon ----------------------------------------------------------
  function gfMultiply(x, y) {
    let z = 0;
    for (let i = 7; i >= 0; i -= 1) {
      z = (z << 1) ^ ((z >>> 7) * 0x11D);
      z ^= ((y >>> i) & 1) * x;
    }
    return z;
  }

  function rsDivisor(degree) {
    const result = new Array(degree).fill(0);
    result[degree - 1] = 1;
    let root = 1;
    for (let i = 0; i < degree; i += 1) {
      for (let j = 0; j < result.length; j += 1) {
        result[j] = gfMultiply(result[j], root);
        if (j + 1 < result.length) result[j] ^= result[j + 1];
      }
      root = gfMultiply(root, 0x02);
    }
    return result;
  }

  function rsRemainder(data, divisor) {
    const result = divisor.map(() => 0);
    for (const b of data) {
      const factor = b ^ result.shift();
      result.push(0);
      divisor.forEach((coefficient, i) => { result[i] ^= gfMultiply(coefficient, factor); });
    }
    return result;
  }

  // ---- data codewords --------------------------------------------------------
  function encodeData(bytes, version, ecc) {
    const bits = [];
    const append = (value, length) => { for (let i = length - 1; i >= 0; i -= 1) bits.push((value >>> i) & 1); };
    append(0x4, 4);                                        // byte mode
    append(bytes.length, version <= 9 ? 8 : 16);           // 文字数
    for (const b of bytes) append(b, 8);
    const capacityBits = dataCodewords(version, ecc) * 8;
    append(0, Math.min(4, capacityBits - bits.length));    // terminator
    // byte 境界までの 0。**Planner の segno 1.6.6 と同じく、既に境界にあるときも 8 bit（0x00 の 1 byte）足す**
    // （`segno.encoder.write_padding_bits` の `8 - (length % 8)`）。terminator の後なので読み取りには影響せず、
    // 同じ URL から Planner と**同じ QR**（同じ module 行列）になる。容量を超えた分は下で切る。
    append(0, 8 - bits.length % 8);
    for (let pad = 0xEC; bits.length < capacityBits; pad ^= 0xEC ^ 0x11) append(pad, 8);
    bits.length = Math.min(bits.length, capacityBits);
    const codewords = [];
    for (let i = 0; i < bits.length; i += 8) {
      let value = 0;
      for (let j = 0; j < 8; j += 1) value = (value << 1) | bits[i + j];
      codewords.push(value);
    }
    return codewords;
  }

  function addEccAndInterleave(data, version, ecc) {
    const numBlocks = NUM_ERROR_CORRECTION_BLOCKS[ecc][version];
    const blockEccLength = ECC_CODEWORDS_PER_BLOCK[ecc][version];
    const rawCodewords = Math.floor(rawDataModules(version) / 8);
    const numShortBlocks = numBlocks - rawCodewords % numBlocks;
    const shortBlockLength = Math.floor(rawCodewords / numBlocks);
    const divisor = rsDivisor(blockEccLength);
    const blocks = [];
    for (let i = 0, k = 0; i < numBlocks; i += 1) {
      const block = data.slice(k, k + shortBlockLength - blockEccLength + (i < numShortBlocks ? 0 : 1));
      k += block.length;
      const eccPart = rsRemainder(block, divisor);
      if (i < numShortBlocks) block.push(0);
      blocks.push(block.concat(eccPart));
    }
    const result = [];
    for (let i = 0; i < blocks[0].length; i += 1) {
      blocks.forEach((block, j) => {
        if (i !== shortBlockLength - blockEccLength || j >= numShortBlocks) result.push(block[i]);
      });
    }
    return result;
  }

  // ---- matrix ----------------------------------------------------------------
  function alignmentPositions(version) {
    if (version === 1) return [];
    const count = Math.floor(version / 7) + 2;
    const step = version === 32 ? 26 : Math.ceil((version * 4 + 4) / (count * 2 - 2)) * 2;
    const result = [6];
    for (let position = version * 4 + 17 - 7; result.length < count; position -= step) result.splice(1, 0, position);
    return result;
  }

  function buildMatrix(version, ecc, codewords, mask) {
    const size = version * 4 + 17;
    const modules = Array.from({ length: size }, () => new Array(size).fill(false));
    const isFunction = Array.from({ length: size }, () => new Array(size).fill(false));
    const reserved = Array.from({ length: size }, () => new Array(size).fill(false));   // format / version / dark module
    const setFunction = (x, y, dark) => { modules[y][x] = dark; isFunction[y][x] = true; };
    const setReserved = (x, y, dark) => { setFunction(x, y, dark); reserved[y][x] = true; };

    for (let i = 0; i < size; i += 1) {
      setFunction(6, i, i % 2 === 0);
      setFunction(i, 6, i % 2 === 0);
    }
    const finder = (cx, cy) => {
      for (let dy = -4; dy <= 4; dy += 1) {
        for (let dx = -4; dx <= 4; dx += 1) {
          const distance = Math.max(Math.abs(dx), Math.abs(dy));
          const x = cx + dx; const y = cy + dy;
          if (x >= 0 && x < size && y >= 0 && y < size) setFunction(x, y, distance !== 2 && distance !== 4);
        }
      }
    };
    finder(3, 3); finder(size - 4, 3); finder(3, size - 4);
    const positions = alignmentPositions(version);
    const last = positions.length - 1;
    positions.forEach((py, i) => positions.forEach((px, j) => {
      if ((i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0)) return;
      for (let dy = -2; dy <= 2; dy += 1) {
        for (let dx = -2; dx <= 2; dx += 1) setFunction(px + dx, py + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
      }
    }));
    const drawFormat = (maskValue) => {
      const data = (ECC_FORMAT_BITS[ecc] << 3) | maskValue;
      let rem = data;
      for (let i = 0; i < 10; i += 1) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
      const bits = ((data << 10) | rem) ^ 0x5412;
      for (let i = 0; i <= 5; i += 1) setReserved(8, i, bit(bits, i));
      setReserved(8, 7, bit(bits, 6));
      setReserved(8, 8, bit(bits, 7));
      setReserved(7, 8, bit(bits, 8));
      for (let i = 9; i < 15; i += 1) setReserved(14 - i, 8, bit(bits, i));
      for (let i = 0; i < 8; i += 1) setReserved(size - 1 - i, 8, bit(bits, i));
      for (let i = 8; i < 15; i += 1) setReserved(8, size - 15 + i, bit(bits, i));
      setReserved(8, size - 8, true);
    };
    drawFormat(0);                                      // 領域の予約（mask 確定後に描き直す）
    if (version >= 7) {
      let rem = version;
      for (let i = 0; i < 12; i += 1) rem = (rem << 1) ^ ((rem >>> 11) * 0x1F25);
      const bits = (version << 12) | rem;
      for (let i = 0; i < 18; i += 1) {
        const a = size - 11 + i % 3; const b = Math.floor(i / 3);
        setReserved(a, b, bit(bits, i));
        setReserved(b, a, bit(bits, i));
      }
    }

    // data（右下から 2 列ずつ、上下に蛇行）
    let index = 0;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (let vertical = 0; vertical < size; vertical += 1) {
        for (let j = 0; j < 2; j += 1) {
          const x = right - j;
          const upward = ((right + 1) & 2) === 0;
          const y = upward ? size - 1 - vertical : vertical;
          if (!isFunction[y][x] && index < codewords.length * 8) {
            modules[y][x] = bit(codewords[index >>> 3], 7 - (index & 7));
            index += 1;
          }
        }
      }
    }

    const applyMask = (maskValue) => {
      for (let y = 0; y < size; y += 1) {
        for (let x = 0; x < size; x += 1) {
          let invert;
          switch (maskValue) {
            case 0: invert = (x + y) % 2 === 0; break;
            case 1: invert = y % 2 === 0; break;
            case 2: invert = x % 3 === 0; break;
            case 3: invert = (x + y) % 3 === 0; break;
            case 4: invert = (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0; break;
            case 5: invert = (x * y) % 2 + (x * y) % 3 === 0; break;
            case 6: invert = ((x * y) % 2 + (x * y) % 3) % 2 === 0; break;
            default: invert = ((x + y) % 2 + (x * y) % 3) % 2 === 0; break;
          }
          if (!isFunction[y][x] && invert) modules[y][x] = !modules[y][x];
        }
      }
    };

    let chosen = mask;
    if (chosen === undefined || chosen === null) {
      let best = Infinity;
      for (let candidate = 0; candidate < 8; candidate += 1) {
        applyMask(candidate);
        const score = penalty(modules, reserved, size);
        if (score < best) { best = score; chosen = candidate; }
        applyMask(candidate);                          // XOR なので同じ mask で元に戻る
      }
    }
    applyMask(chosen);
    drawFormat(chosen);
    return { size, modules, mask: chosen };
  }

  // mask の評価（ISO/IEC 18004 7.8.3）。**Planner の segno 1.6.6（`segno.encoder.mask_scores`）と同じ数え方**にして、
  // 同じ入力から同じ mask を選ぶ（= Planner と同じ QR）。segno と同じく、format / version 情報と dark module は
  // まだ書いていない（明るい）状態で数える。
  function penalty(modules, reserved, size) {
    const cell = (y, x) => (reserved[y][x] ? 0 : (modules[y][x] ? 1 : 0));
    const pattern = [1, 0, 1, 1, 1, 0, 1];
    const occurrences = (seq) => {
      const find = (from) => {
        for (let i = from; i <= seq.length - 7; i += 1) {
          let ok = true;
          for (let k = 0; k < 7; k += 1) if (seq[i + k] !== pattern[k]) { ok = false; break; }
          if (ok) return i;
        }
        return -1;
      };
      const anyDark = (from, to) => { for (let k = Math.max(from, 0); k < Math.min(to, size); k += 1) if (seq[k]) return true; return false; };
      let count = 0;
      let index = find(0);
      while (index !== -1) {
        let offset = index + 7;
        if (index === 0 || index === size - 7 || !anyDark(index - 4, index) || !anyDark(offset, offset + 4)) count += 40;
        else offset = index + 4;
        index = find(offset);
      }
      return count;
    };
    let n1 = 0; let n2 = 0; let n3 = 0; let dark = 0;
    for (let i = 0; i < size; i += 1) {
      let rowPrev = -1; let colPrev = -1; let rowRun = 0; let colRun = 0;
      const row = []; const column = [];
      for (let j = 0; j < size; j += 1) {
        const r = cell(i, j); const c = cell(j, i);
        row.push(r); column.push(c);
        dark += r;
        if (r === rowPrev) rowRun += 1; else { if (rowRun >= 5) n1 += rowRun - 2; rowRun = 1; }
        if (c === colPrev) colRun += 1; else { if (colRun >= 5) n1 += colRun - 2; colRun = 1; }
        if (i > 0 && j > 0 && r === rowPrev && r === cell(i - 1, j) && r === cell(i - 1, j - 1)) n2 += 3;
        rowPrev = r; colPrev = c;
      }
      n3 += occurrences(row) + occurrences(column);
      if (rowRun >= 5) n1 += rowRun - 2;
      if (colRun >= 5) n1 += colRun - 2;
    }
    const n4 = 10 * Math.trunc(Math.abs(dark / (size * size) * 100 - 50) / 5);
    return n1 + n2 + n3 + n4;
  }

  // text → {version, ecc, mask, size, modules}
  // options: {ecc: "M"（既定）, version（固定したいとき）, mask（固定したいとき）}
  function encode(text, options = {}) {
    if (typeof text !== "string" || text === "") throw new QrError("QR_GENERATION_FAILED", "text is empty");
    const ecc = ECC[options.ecc || "M"];
    if (ecc === undefined) throw new QrError("QR_GENERATION_FAILED", "unknown ecc level");
    const bytes = Array.from(new TextEncoder().encode(text));
    let version = options.version || 0;
    if (!version) {
      for (let v = 1; v <= 40; v += 1) {
        if (4 + (v <= 9 ? 8 : 16) + bytes.length * 8 <= dataCodewords(v, ecc) * 8) { version = v; break; }
      }
    }
    if (!version || 4 + (version <= 9 ? 8 : 16) + bytes.length * 8 > dataCodewords(version, ecc) * 8) {
      throw new QrError("QR_CAPACITY_EXCEEDED", "the text is too long for a QR code (" + bytes.length + " B)");
    }
    const codewords = addEccAndInterleave(encodeData(bytes, version, ecc), version, ecc);
    const matrix = buildMatrix(version, ecc, codewords, options.mask);
    return { version, ecc: options.ecc || "M", mask: matrix.mask, size: matrix.size, modules: matrix.modules, byteLength: bytes.length };
  }

  // module 行列 → PNG（黒 / 白のみ）。1 module = scale px（整数）、quiet zone = border module。補間しない。
  function toPngBlob(qr, options = {}) {
    const scale = options.scale || 10;
    const border = options.border === undefined ? 4 : options.border;
    if (!Number.isInteger(scale) || scale < 1 || !Number.isInteger(border) || border < 0) {
      return Promise.reject(new QrError("PNG_SERIALIZATION_FAILED", "scale and border must be integers"));
    }
    const side = (qr.size + 2 * border) * scale;
    const canvas = document.createElement("canvas");
    canvas.width = side;
    canvas.height = side;
    const context = canvas.getContext("2d");
    context.imageSmoothingEnabled = false;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, side, side);
    context.fillStyle = "#000000";
    for (let y = 0; y < qr.size; y += 1) {
      for (let x = 0; x < qr.size; x += 1) {
        if (qr.modules[y][x]) context.fillRect((x + border) * scale, (y + border) * scale, scale, scale);
      }
    }
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob)
        : reject(new QrError("PNG_SERIALIZATION_FAILED", "the QR could not be encoded as PNG"))), "image/png");
    });
  }

  root.SidekickQr = Object.freeze({ encode, toPngBlob, QrError, MAX_BYTES_ECC_M: 2331 });
})(typeof window === "undefined" ? globalThis : window);
