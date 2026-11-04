import type { LinkedInFields } from '../../api/types';

/** LinkedIn's add-certification form, prefilled from the fields the API computed. */
export function addToProfileUrl(fields: LinkedInFields): string {
  const query = [
    ['startTask', 'CERTIFICATION_NAME'],
    ['name', fields.name],
    ['organizationName', fields.organisation],
    ['issueYear', String(fields.issue_year)],
    ['issueMonth', String(fields.issue_month)],
    ['certUrl', fields.credential_url],
    ['certId', fields.credential_id],
  ]
    .map(([key, value]) => `${key}=${encodeURIComponent(value ?? '')}`)
    .join('&');
  return `https://www.linkedin.com/profile/add?${query}`;
}

/** LinkedIn's share dialog for a public page. */
export function shareUrl(publicUrl: string): string {
  return `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(publicUrl)}`;
}
