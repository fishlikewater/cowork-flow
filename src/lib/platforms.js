import { hostRegistry } from './host-assets.js';


export const SUPPORTED_PLATFORMS = [...hostRegistry.platformIds];


export function parsePlatformSelection(values) {
  return hostRegistry.parsePlatformSelection(values);
}


export function formatPlatformList(platforms) {
  return platforms.join(', ');
}


export function platformLabel(platform) {
  return hostRegistry.platformLabel(platform);
}
