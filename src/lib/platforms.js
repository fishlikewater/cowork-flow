import { hostRegistry } from './host-assets.js';


export const SUPPORTED_PLATFORMS = [...hostRegistry.platformIds];


export function supportedPlatformMessage() {
  return SUPPORTED_PLATFORMS.join(', ');
}


export function parsePlatformSelection(values) {
  return hostRegistry.parsePlatformSelection(values);
}


export function formatPlatformList(platforms) {
  return platforms.join(', ');
}


export function shouldIncludeForPlatforms(relativePath, platforms) {
  return hostRegistry.shouldInclude(relativePath, platforms);
}


export function skillDestinationForPlatform(platform) {
  return hostRegistry.skillDestination(platform);
}


export function platformLabel(platform) {
  return hostRegistry.platformLabel(platform);
}
