const NEWLINE = /\r?\n/;
const textDecoder = new TextDecoder();

export async function* parseNdjsonStream<T = unknown>(response: Response): AsyncGenerator<T> {
  const body = response.body;
  if (!body) {
    throw new Error("Response body is not a readable stream.");
  }

  const reader = body.getReader();
  let buffer = "";

  try {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += textDecoder.decode(value, { stream: true });

      while (true) {
        const newlineIndex = buffer.search(NEWLINE);
        if (newlineIndex === -1) {
          break;
        }

        const line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + (buffer[newlineIndex] === "\r" ? 2 : 1));

        const trimmed = line.trim();
        if (!trimmed) {
          continue;
        }

        yield JSON.parse(trimmed) as T;
      }
    }

    buffer += textDecoder.decode();
    const leftover = buffer.trim();
    if (leftover) {
      yield JSON.parse(leftover) as T;
    }
  } finally {
    reader.releaseLock();
  }
}
