// src/polyfills.ts

// Only run in browser
if (typeof window !== 'undefined') {
  const win = window as any;

  if (!win.crypto) {
    win.crypto = {};
  }

  if (typeof win.crypto.randomUUID !== 'function') {
    // Simple RFC4122-ish UUID v4 polyfill
    win.crypto.randomUUID = function randomUUID() {
      const bytes = new Uint8Array(16);

      if (win.crypto.getRandomValues) {
        win.crypto.getRandomValues(bytes);
      } else {
        // Fallback to Math.random if getRandomValues isn't available
        for (let i = 0; i < 16; i++) {
          bytes[i] = Math.floor(Math.random() * 256);
        }
      }

      // Convert to UUID string
      bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
      bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant

      const hex: string[] = [];
      for (let i = 0; i < 256; i++) {
        hex.push((i + 0x100).toString(16).substring(1));
      }

      return (
        hex[bytes[0]] +
        hex[bytes[1]] +
        hex[bytes[2]] +
        hex[bytes[3]] +
        '-' +
        hex[bytes[4]] +
        hex[bytes[5]] +
        '-' +
        hex[bytes[6]] +
        hex[bytes[7]] +
        '-' +
        hex[bytes[8]] +
        hex[bytes[9]] +
        '-' +
        hex[bytes[10]] +
        hex[bytes[11]] +
        hex[bytes[12]] +
        hex[bytes[13]] +
        hex[bytes[14]] +
        hex[bytes[15]]
      );
    };
  }
}
