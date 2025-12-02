/**
 * Asset Display - Shows outputs from agents.
 *
 * Features:
 * - Strategy assets (personas, slogans)
 * - Art Director assets (hero images)
 * - Video Producer assets (social media clips)
 * - Audio Team assets (jingles, voiceovers, podcast ads)
 * - Web Dev assets (landing page preview)
 */

'use client';

import { useProjectStore } from '@/stores/useProjectStore';
import { cn } from '@/lib/utils';
import { useState, useEffect, useMemo } from 'react';
import { ExternalLink, Maximize2, X, Target, Palette, Film, Music, Code } from 'lucide-react';

interface AssetDisplayProps {
  sendMessage?: (message: any) => void;
}

export function AssetDisplay({ sendMessage }: AssetDisplayProps) {
  const { assets } = useProjectStore();

  const hasAssets = Object.keys(assets).length > 0;

  if (!hasAssets) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500">
        <div className="text-center">
          <Palette className="w-16 h-16 mx-auto mb-4 text-zinc-600" />
          <div className="text-lg">Waiting for creative assets...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="max-w-6xl mx-auto space-y-4">
        {assets.strategy && <StrategyAssets data={assets.strategy} />}
        {assets.art_director && <ArtDirectorAssets data={assets.art_director} sendMessage={sendMessage} />}
        {assets.video_producer && <VideoProducerAssets data={assets.video_producer} />}
        {assets.audio_team && <AudioTeamAssets data={assets.audio_team} />}
        {assets.web_dev && <WebDevAssets data={assets.web_dev} />}
      </div>
    </div>
  );
}

function StrategyAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-4">
      <h3 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
        <Target className="w-5 h-5 text-purple-400" />
        Strategy & Personas
      </h3>

      {/* Personas */}
      {assetData.personas && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-zinc-400 mb-3">Customer Personas</h4>
          <div className="grid grid-cols-3 gap-4">
            {assetData.personas.map((persona: any, i: number) => (
              <div key={i} className="bg-zinc-800 rounded p-4 border border-zinc-700">
                <div className="font-medium text-white mb-2">{persona.name}</div>
                <div className="text-sm text-zinc-400 mb-2">{persona.description}</div>
                <div className="text-xs text-zinc-500">{persona.motivation}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slogans */}
      {assetData.slogans && (
        <div>
          <h4 className="text-sm font-medium text-zinc-400 mb-3">Campaign Slogans</h4>
          <div className="space-y-2">
            {assetData.slogans.map((slogan: string, i: number) => (
              <div
                key={i}
                className="bg-zinc-800 rounded px-4 py-3 border border-zinc-700 text-white"
              >
                {i + 1}. {slogan}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface ArtDirectorAssetsProps {
  data: any[];
  sendMessage?: (message: any) => void;
}

function ArtDirectorAssets({ data, sendMessage }: ArtDirectorAssetsProps) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;
  const [selectedImage, setSelectedImage] = useState<number | null>(null);
  const [showVersionHistory, setShowVersionHistory] = useState<{ [key: number]: boolean }>({});
  // Track which version is displayed for each image position (default to current version)
  const [displayedVersions, setDisplayedVersions] = useState<{ [key: number]: any }>({});
  // Modal state for full-size image view
  const [expandedImage, setExpandedImage] = useState<{ url: string; description: string } | null>(null);

  const handleImageSelect = (index: number, image: any) => {
    setSelectedImage(index);

    // Send selection to backend to update project brief
    if (sendMessage) {
      sendMessage({
        type: 'update_brief',
        data: {
          selected_image_url: image.url,
        },
      });
      // Don't log full base64 data URL - just show size
      const dataSizeKB = image.url?.startsWith('data:')
        ? Math.round(image.url.length / 1024)
        : null;
      console.log('[AssetDisplay] Sent image selection to backend, size:', dataSizeKB ? `${dataSizeKB}KB` : 'N/A');
    }
  };

  // Get refinement history for a specific image
  const getVersionHistory = (image: any) => {
    if (!assetData.refinement_history) return [];

    // For refined images (refinement_iteration > 0), use parent_asset_id to look up history
    // For original images (refinement_iteration === 0), use asset_id
    const assetId = image.parent_asset_id || image.asset_id;
    if (!assetId) return [];

    const history = assetData.refinement_history[assetId];
    if (!history) return [];

    // Build version list: [original, v1, v2, v3, ...]
    const versions = [];

    // Find original (refinement_iteration === 0)
    if (image.refinement_iteration === 0) {
      versions.push({ version: 0, image, label: 'v0 (original)' });
    } else {
      // Original is in history.refinements
      const original = history.refinements?.find((r: any) => r.refinement_iteration === 0);
      if (original) {
        versions.push({ version: 0, image: original, label: 'v0 (original)' });
      }
    }

    // Add all refinements
    history.refinements?.forEach((refinement: any) => {
      if (refinement.refinement_iteration > 0) {
        versions.push({
          version: refinement.refinement_iteration,
          image: refinement,
          label: `v${refinement.refinement_iteration}`,
          feedback: history.feedback_history?.[refinement.refinement_iteration - 1]
        });
      }
    });

    // Add current if it's a refinement
    if (image.refinement_iteration > 0 && !versions.find(v => v.version === image.refinement_iteration)) {
      versions.push({
        version: image.refinement_iteration,
        image,
        label: `v${image.refinement_iteration} (current)`,
        feedback: image.user_feedback_applied
      });
    }

    return versions.sort((a, b) => a.version - b.version);
  };

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-4">
      <h3 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
        <Palette className="w-5 h-5 text-purple-400" />
        Hero Images
        {assetData.current_generation && (
          <span className="text-xs text-zinc-500">
            Generation {assetData.current_generation}
          </span>
        )}
      </h3>

      <div className="grid grid-cols-2 gap-4">
        {assetData.images?.map((image: any, i: number) => {
          const versionHistory = getVersionHistory(image);
          const hasVersions = versionHistory.length > 1;

          // Use displayed version if set, otherwise use default image
          const displayedImage = displayedVersions[i] || image;
          const displayedVersion = displayedImage.refinement_iteration || 0;

          return (
            <div key={i} className="relative">
              <div
                className={cn(
                  'cursor-pointer rounded-lg border-2 transition-all overflow-hidden',
                  selectedImage === i ? 'border-blue-500 ring-2 ring-blue-500/50' : 'border-zinc-700'
                )}
                onClick={() => handleImageSelect(i, displayedImage)}
              >
                <div className="relative group">
                  <img src={displayedImage.url} alt={displayedImage.description || 'Hero image'} className="w-full aspect-video object-cover" />
                  {/* Expand button overlay */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setExpandedImage({
                        url: displayedImage.url,
                        description: displayedImage.description || displayedImage.generation_params?.prompt || 'Hero image'
                      });
                    }}
                    className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-black/80 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                    title="View full size"
                  >
                    <Maximize2 className="w-4 h-4 text-white" />
                  </button>
                </div>
                <div className="p-3 bg-zinc-800">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-xs text-zinc-400 flex-1">
                      {displayedImage.description || displayedImage.generation_params?.prompt || 'Hero image'}
                    </div>
                    {hasVersions && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowVersionHistory(prev => ({ ...prev, [i]: !prev[i] }));
                        }}
                        className="text-xs px-2 py-1 bg-zinc-700 hover:bg-zinc-600 rounded transition-colors text-white shrink-0"
                      >
                        v{displayedVersion} ▾
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Version History Dropdown */}
              {showVersionHistory[i] && hasVersions && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl z-10 overflow-hidden">
                  <div className="p-2 border-b border-zinc-700 text-xs font-medium text-zinc-400">
                    Version History
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {versionHistory.map((v) => (
                      <div
                        key={v.version}
                        className={cn(
                          'p-3 hover:bg-zinc-700 cursor-pointer transition-colors border-b border-zinc-700/50',
                          v.version === displayedVersion && 'bg-zinc-700/50'
                        )}
                        onClick={(e) => {
                          e.stopPropagation();
                          // Swap to this version
                          setDisplayedVersions(prev => ({ ...prev, [i]: v.image }));
                          // Close dropdown
                          setShowVersionHistory(prev => ({ ...prev, [i]: false }));
                          console.log('Switched to version', v.version, 'for image', i);
                        }}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-white">{v.label}</span>
                          {v.version === displayedVersion && (
                            <span className="text-xs text-blue-400">Viewing</span>
                          )}
                        </div>
                        {v.feedback && (
                          <div className="text-xs text-zinc-400 italic">
                            "{v.feedback}"
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Full-size Image Modal */}
      {expandedImage && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={() => setExpandedImage(null)}
        >
          <button
            onClick={() => setExpandedImage(null)}
            className="absolute top-4 right-4 p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
            title="Close"
          >
            <X className="w-6 h-6 text-white" />
          </button>
          <div
            className="max-w-[90vw] max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={expandedImage.url}
              alt={expandedImage.description}
              className="max-w-full max-h-[85vh] object-contain rounded-lg"
            />
            <div className="mt-3 text-center text-sm text-zinc-400">
              {expandedImage.description}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function VideoProducerAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-4">
      <h3 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
        <Film className="w-5 h-5 text-purple-400" />
        Social Media Video
      </h3>

      {assetData.video?.url && (
        <video
          src={assetData.video.url}
          controls
          className="w-full rounded-lg border border-zinc-700"
        />
      )}

      {assetData.video?.generation_params?.prompt && (
        <div className="mt-4 text-sm text-zinc-400">
          <span className="font-medium">Prompt:</span> {assetData.video.generation_params.prompt}
        </div>
      )}

      {assetData.critique_notes && (
        <div className="mt-2 text-sm text-zinc-500">
          <span className="font-medium">Critique Notes:</span> {assetData.critique_notes}
        </div>
      )}
    </div>
  );
}

function AudioTeamAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-4">
      <h3 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
        <Music className="w-5 h-5 text-purple-400" />
        Audio Assets
      </h3>

      <div className="space-y-4">
        {assetData.jingle?.url && (
          <div>
            <div className="text-sm font-medium text-zinc-400 mb-2">Jingle</div>
            <audio src={assetData.jingle.url} controls className="w-full" />
            {assetData.jingle.duration_seconds && (
              <div className="mt-1 text-xs text-zinc-500">Duration: {assetData.jingle.duration_seconds}s</div>
            )}
          </div>
        )}

        {assetData.podcast_ad?.url && (
          <div>
            <div className="text-sm font-medium text-zinc-400 mb-2">Podcast Ad</div>
            <audio src={assetData.podcast_ad.url} controls className="w-full" />
            {assetData.podcast_ad.script && (
              <div className="mt-2 text-xs text-zinc-500 italic bg-zinc-800 rounded p-2">
                "{assetData.podcast_ad.script}"
              </div>
            )}
          </div>
        )}

        {assetData.transcription?.text && (
          <div>
            <div className="text-sm font-medium text-zinc-400 mb-2">Transcription</div>
            <div className="text-xs text-zinc-400 bg-zinc-800 rounded p-3 whitespace-pre-wrap">
              {assetData.transcription.text}
            </div>
          </div>
        )}

        {assetData.proactive_suggestion && (
          <div className="bg-blue-900/20 border border-blue-800 rounded p-3">
            <div className="text-sm font-medium text-blue-400 mb-1">💡 Agent Suggestion</div>
            <div className="text-sm text-blue-300">{assetData.proactive_suggestion}</div>
          </div>
        )}
      </div>
    </div>
  );
}

function WebDevAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;

  // Extract HTML, CSS, JS from the nested code object
  const code = assetData.code;
  const html = code?.html || '';
  const css = code?.css || '';
  const js = code?.javascript || '';

  // Create and manage iframe source
  const [iframeSrc, setIframeSrc] = useState<string>('');

  useEffect(() => {
    // If we have a preview_url (backend API URL), use it directly
    if (code?.preview_url) {
      setIframeSrc(code.preview_url);
    } else {
      setIframeSrc('');
    }
  }, [code?.preview_url]);

  // Handler to open landing page in new window
  const handleOpenInBrowser = () => {
    if (code?.preview_url) {
      window.open(code.preview_url, '_blank');
    }
  };

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold text-white flex items-center gap-2">
          <Code className="w-5 h-5 text-purple-400" />
          Landing Page
        </h3>
        {code && (
          <button
            onClick={handleOpenInBrowser}
            disabled={!code.preview_url}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 hover:border-zinc-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={code.preview_url ? "Open in new tab" : "Preview unavailable"}
          >
            <ExternalLink className="w-4 h-4" />
            <span>Open in Browser</span>
          </button>
        )}
      </div>

      {code && iframeSrc && (
        <div className="space-y-4">
          <div className="border border-zinc-700 rounded-lg overflow-hidden bg-white">
            <iframe
              src={iframeSrc}
              className="w-full h-[600px]"
              title="Landing page preview"
              sandbox="allow-scripts allow-same-origin"
            />
          </div>

          <div className="flex gap-2 text-xs text-zinc-500">
            <span>HTML: {html.length} chars</span>
            <span>•</span>
            <span>CSS: {css.length} chars</span>
            <span>•</span>
            <span>JS: {js.length} chars</span>
          </div>
        </div>
      )}

      {code && !iframeSrc && (
        <div className="text-sm text-zinc-500 p-4 text-center border border-zinc-800 rounded-lg bg-zinc-900/50">
          Preview unavailable (Upload failed or pending)
        </div>
      )}

      {!code && (
        <div className="text-sm text-zinc-500">No landing page code available</div>
      )}
    </div>
  );
}
