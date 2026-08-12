import assert from 'node:assert/strict';
import test from 'node:test';
import { sha256Buffer } from '../modules/asset-integrity';

test('sha256Buffer falls back when WebCrypto subtle digest is unavailable', async () => {
  const digest = await sha256Buffer(new TextEncoder().encode('abc').buffer, undefined);

  assert.equal(digest, 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
});
