export type PreprocessingFilter = 'none' | 'lee_speckle' | 'clahe' | 'waterfall_normalize';

export interface PreprocessingOptions {
  filter: PreprocessingFilter;
  contrastGain?: number;
  speckleDamping?: number;
}

/**
 * Modular Sonar Image Preprocessing Interface.
 * Structured to apply acoustic speckle reduction (Lee filter) and CLAHE in Phase 2.
 */
export async function preprocessSonarImage(
  imageSrc: string,
  options: PreprocessingOptions = { filter: 'none' }
): Promise<string> {
  // For MVP, return original image source.
  if (options.filter === 'none') {
    return imageSrc;
  }

  // Placeholder for client-side or backend filter pipeline
  console.info(`[SonarPreprocessor] Filter '${options.filter}' queued for Phase 2 pipeline.`);
  return imageSrc;
}
