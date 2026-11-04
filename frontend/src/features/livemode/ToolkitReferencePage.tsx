import { KitDocPage } from './LiveModeGuidePage';

/** Served by the API from docs/toolkit-reference.md: the kit is public, like the wheel. */
export const TOOLKIT_REFERENCE_SOURCE = '/kit/toolkit-reference.md';

/** The toolkit reference (docs/toolkit-reference.md), linked from the workspace. */
export function ToolkitReferencePage() {
  return (
    <KitDocPage
      source={TOOLKIT_REFERENCE_SOURCE}
      title="Toolkit reference"
      summary="Every name you can import from forgeway_kit, with its fields."
    />
  );
}
