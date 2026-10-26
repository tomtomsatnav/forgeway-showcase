import { describe, expect, it } from 'vitest';

import type { LinkedInFields } from '../../api/types';
import { addToProfileUrl, shareUrl } from './linkedin';

const FIELDS: LinkedInFields = {
  name: 'Forgeway Foundations track',
  organisation: 'Forgeway',
  issue_year: 2026,
  issue_month: 10,
  credential_id: 'abc_DEF-123',
  credential_url: 'https://forgeway.example/c/abc_DEF-123',
};

describe('addToProfileUrl', () => {
  it('prefills the add-certification form from the API fields', () => {
    const url = new URL(addToProfileUrl(FIELDS));

    expect(`${url.origin}${url.pathname}`).toBe('https://www.linkedin.com/profile/add');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      startTask: 'CERTIFICATION_NAME',
      name: 'Forgeway Foundations track',
      organizationName: 'Forgeway',
      issueYear: '2026',
      issueMonth: '10',
      certUrl: 'https://forgeway.example/c/abc_DEF-123',
      certId: 'abc_DEF-123',
    });
  });

  it('encodes spaces, ampersands and the credential URL', () => {
    const href = addToProfileUrl({ ...FIELDS, name: 'Protocols & tools' });

    expect(href).toContain('name=Protocols%20%26%20tools');
    expect(href).toContain('certUrl=https%3A%2F%2Fforgeway.example%2Fc%2Fabc_DEF-123');
    expect(href).not.toContain(' ');
  });

  it('round-trips non-ASCII names', () => {
    const name = 'Zoë Müller-Łukasiewicz 日本語';
    const url = new URL(addToProfileUrl({ ...FIELDS, name }));

    expect(url.searchParams.get('name')).toBe(name);
    expect(url.search).not.toMatch(/[^\x20-\x7e]/);
  });
});

describe('shareUrl', () => {
  it('shares the encoded public URL', () => {
    const href = shareUrl('https://forgeway.example/c/abc?x=1&y=2');

    expect(href).toBe(
      'https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fforgeway.example%2Fc%2Fabc%3Fx%3D1%26y%3D2',
    );
    expect(new URL(href).searchParams.get('url')).toBe('https://forgeway.example/c/abc?x=1&y=2');
  });
});
