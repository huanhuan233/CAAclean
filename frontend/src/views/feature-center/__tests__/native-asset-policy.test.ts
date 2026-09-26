import assert from 'node:assert/strict';
import test from 'node:test';
import { nativeAssetLoadPolicy } from '../modules/native-asset-policy';

test('PostgreSQL native tree suppresses duplicate whole-bundle JSONL downloads', () => {
  assert.deepEqual(
    nativeAssetLoadPolicy({ loadedNativeTreeFromApi: true, sourceFormat: 'CATPRODUCT', status: 'ready' }),
    {
      loadProductOccurrencesJsonl: false,
      loadFeaturesJsonl: false,
      loadParametersJsonl: false,
      loadPropertyFactsJsonl: false,
      loadHeavySemanticsJsonl: false
    }
  );
});

test('legacy asset fallback remains available only when the database tree was unavailable', () => {
  assert.deepEqual(
    nativeAssetLoadPolicy({ loadedNativeTreeFromApi: false, sourceFormat: 'CATPRODUCT', status: 'ready' }),
    {
      loadProductOccurrencesJsonl: true,
      loadFeaturesJsonl: false,
      loadParametersJsonl: false,
      loadPropertyFactsJsonl: false,
      loadHeavySemanticsJsonl: false
    }
  );
});

test('legacy CATPart without a database tree may load its feature JSONL', () => {
  assert.equal(
    nativeAssetLoadPolicy({ loadedNativeTreeFromApi: false, sourceFormat: 'CATPART', status: 'ready' })
      .loadFeaturesJsonl,
    true
  );
});

test('CATPart processing state never requests unpublished heavy semantic assets', () => {
  assert.equal(
    nativeAssetLoadPolicy({ loadedNativeTreeFromApi: true, sourceFormat: 'CATPART', status: 'processing' })
      .loadHeavySemanticsJsonl,
    false
  );
});

test('ready CATPart may load published topology assets', () => {
  assert.equal(
    nativeAssetLoadPolicy({ loadedNativeTreeFromApi: true, sourceFormat: 'CATPART', status: 'ready' })
      .loadHeavySemanticsJsonl,
    true
  );
});
