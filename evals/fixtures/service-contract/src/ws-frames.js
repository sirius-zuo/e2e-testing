import { randomBytes } from "node:crypto";

/**
 * Minimal RFC 6455 text-frame codec for the service-contract fixture.
 * Supports only single, unfragmented text (opcode 0x1) and close (0x8) frames
 * with payloads under 65536 bytes, which is all the fixture protocol needs.
 */

export function encodeFrame(payloadObj, { mask = false } = {}) {
  const payload = Buffer.from(JSON.stringify(payloadObj));
  const length = payload.length;
  const maskBit = mask ? 0x80 : 0x00;
  let header;
  if (length < 126) {
    header = Buffer.from([0x81, maskBit | length]);
  } else if (length < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x81;
    header[1] = maskBit | 126;
    header.writeUInt16BE(length, 2);
  } else {
    throw new Error("payload too large for fixture websocket frame");
  }
  if (!mask) {
    return Buffer.concat([header, payload]);
  }
  const maskKey = randomBytes(4);
  const maskedPayload = Buffer.alloc(length);
  for (let i = 0; i < length; i++) {
    maskedPayload[i] = payload[i] ^ maskKey[i % 4];
  }
  return Buffer.concat([header, maskKey, maskedPayload]);
}

export function decodeFrames(buffer) {
  const messages = [];
  let offset = 0;
  while (offset + 2 <= buffer.length) {
    const byte1 = buffer[offset];
    const byte2 = buffer[offset + 1];
    const opcode = byte1 & 0x0f;
    const masked = (byte2 & 0x80) !== 0;
    let length = byte2 & 0x7f;
    let cursor = offset + 2;
    if (length === 126) {
      if (buffer.length < cursor + 2) break;
      length = buffer.readUInt16BE(cursor);
      cursor += 2;
    } else if (length === 127) {
      break; // fixture does not support 64-bit frame lengths
    }
    let maskKey = null;
    if (masked) {
      if (buffer.length < cursor + 4) break;
      maskKey = buffer.subarray(cursor, cursor + 4);
      cursor += 4;
    }
    if (buffer.length < cursor + length) break;
    let payload = buffer.subarray(cursor, cursor + length);
    if (masked) {
      const unmasked = Buffer.alloc(length);
      for (let i = 0; i < length; i++) {
        unmasked[i] = payload[i] ^ maskKey[i % 4];
      }
      payload = unmasked;
    }
    if (opcode === 0x8) {
      messages.push({ __close: true });
    } else if (opcode === 0x1) {
      messages.push(JSON.parse(payload.toString("utf8")));
    }
    offset = cursor + length;
  }
  return { messages, remainder: buffer.subarray(offset) };
}
