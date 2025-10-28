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
import { useState } from 'react';

export function AssetDisplay() {
  const { assets } = useProjectStore();

  const hasAssets = Object.keys(assets).length > 0;

  if (!hasAssets) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500">
        <div className="text-center">
          <div className="text-6xl mb-4">🎨</div>
          <div className="text-lg">Waiting for creative assets...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {assets.strategy && <StrategyAssets data={assets.strategy} />}
        {assets.art_director && <ArtDirectorAssets data={assets.art_director} />}
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
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        🎯 Strategy & Personas
      </h3>

      {/* Personas */}
      {assetData.personas && (
        <div className="mb-6">
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

function ArtDirectorAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;
  const [selectedImage, setSelectedImage] = useState<number | null>(null);

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        🎨 Hero Images
      </h3>

      <div className="grid grid-cols-2 gap-4">
        {assetData.images?.map((image: any, i: number) => (
          <div
            key={i}
            className={cn(
              'cursor-pointer rounded-lg border-2 transition-all overflow-hidden',
              selectedImage === i ? 'border-blue-500 ring-2 ring-blue-500/50' : 'border-zinc-700'
            )}
            onClick={() => setSelectedImage(i)}
          >
            <img src={image.url} alt={image.prompt} className="w-full aspect-video object-cover" />
            <div className="p-3 bg-zinc-800">
              <div className="text-xs text-zinc-400">{image.prompt}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VideoProducerAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        🎬 Social Media Video
      </h3>

      {assetData.video_url && (
        <video
          src={assetData.video_url}
          controls
          className="w-full rounded-lg border border-zinc-700"
        />
      )}

      {assetData.prompt && (
        <div className="mt-4 text-sm text-zinc-400">
          <span className="font-medium">Prompt:</span> {assetData.prompt}
        </div>
      )}
    </div>
  );
}

function AudioTeamAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        🎵 Audio Assets
      </h3>

      <div className="space-y-4">
        {assetData.jingle_url && (
          <div>
            <div className="text-sm font-medium text-zinc-400 mb-2">Jingle</div>
            <audio src={assetData.jingle_url} controls className="w-full" />
          </div>
        )}

        {assetData.voiceover_url && (
          <div>
            <div className="text-sm font-medium text-zinc-400 mb-2">Voiceover</div>
            <audio src={assetData.voiceover_url} controls className="w-full" />
            {assetData.voiceover_script && (
              <div className="mt-2 text-xs text-zinc-500 italic">{assetData.voiceover_script}</div>
            )}
          </div>
        )}

        {assetData.podcast_ad_url && (
          <div>
            <div className="text-sm font-medium text-zinc-400 mb-2">Podcast Ad</div>
            <audio src={assetData.podcast_ad_url} controls className="w-full" />
          </div>
        )}
      </div>
    </div>
  );
}

function WebDevAssets({ data }: { data: any[] }) {
  const latestAsset = data[data.length - 1];
  const assetData = latestAsset.data;

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        💻 Landing Page
      </h3>

      {assetData.preview_url && (
        <div className="border border-zinc-700 rounded-lg overflow-hidden">
          <iframe
            src={assetData.preview_url}
            className="w-full h-96"
            title="Landing page preview"
          />
        </div>
      )}

      {assetData.deploy_url && (
        <a
          href={assetData.deploy_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-blue-400 hover:text-blue-300 text-sm"
        >
          View live page →
        </a>
      )}
    </div>
  );
}
