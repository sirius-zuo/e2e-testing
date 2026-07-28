/**
 * Minimal hand-rolled protobuf codec for the fixture's single-method
 * OrderService (see contracts/service.proto), plus gRPC's length-prefixed
 * message framing. Supports only the string and repeated-string fields
 * that GetOrderRequest/GetOrderResponse actually declare.
 */

function encodeVarint(value) {
  const bytes = [];
  let v = value >>> 0;
  do {
    let byte = v & 0x7f;
    v >>>= 7;
    if (v) byte |= 0x80;
    bytes.push(byte);
  } while (v);
  return Buffer.from(bytes);
}

function decodeVarint(buffer, offset) {
  let result = 0;
  let shift = 0;
  let position = offset;
  let byte;
  do {
    byte = buffer[position];
    result |= (byte & 0x7f) << shift;
    position += 1;
    shift += 7;
  } while (byte & 0x80);
  return { value: result >>> 0, offset: position };
}

function encodeStringField(fieldNumber, value) {
  const payload = Buffer.from(value || "", "utf8");
  return Buffer.concat([
    encodeVarint((fieldNumber << 3) | 2),
    encodeVarint(payload.length),
    payload,
  ]);
}

function decodeFields(buffer) {
  const fields = new Map();
  let offset = 0;
  while (offset < buffer.length) {
    const tag = decodeVarint(buffer, offset);
    offset = tag.offset;
    const fieldNumber = tag.value >>> 3;
    const wireType = tag.value & 0x7;
    if (wireType !== 2) {
      throw new Error(`unsupported wire type in fixture codec: ${wireType}`);
    }
    const length = decodeVarint(buffer, offset);
    offset = length.offset;
    const value = buffer.subarray(offset, offset + length.value);
    offset += length.value;
    if (!fields.has(fieldNumber)) fields.set(fieldNumber, []);
    fields.get(fieldNumber).push(value);
  }
  return fields;
}

export function encodeGetOrderRequest({ id }) {
  return encodeStringField(1, id);
}

export function decodeGetOrderRequest(buffer) {
  const fields = decodeFields(buffer);
  const id = (fields.get(1) || [Buffer.alloc(0)])[0];
  return { id: id.toString("utf8") };
}

export function encodeGetOrderResponse({ id, status, items }) {
  const parts = [encodeStringField(1, id), encodeStringField(2, status)];
  for (const item of items || []) {
    parts.push(encodeStringField(3, item));
  }
  return Buffer.concat(parts);
}

export function decodeGetOrderResponse(buffer) {
  const fields = decodeFields(buffer);
  const id = (fields.get(1) || [Buffer.alloc(0)])[0].toString("utf8");
  const status = (fields.get(2) || [Buffer.alloc(0)])[0].toString("utf8");
  const items = (fields.get(3) || []).map((value) => value.toString("utf8"));
  return { id, status, items };
}

export function frameMessage(payload) {
  const header = Buffer.alloc(5);
  header.writeUInt8(0, 0);
  header.writeUInt32BE(payload.length, 1);
  return Buffer.concat([header, payload]);
}

export function unframeMessage(buffer) {
  if (buffer.length < 5) return null;
  const length = buffer.readUInt32BE(1);
  if (buffer.length < 5 + length) return null;
  return { payload: buffer.subarray(5, 5 + length), remainder: buffer.subarray(5 + length) };
}
