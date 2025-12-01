/**
 * Reference Images Display - Display user-uploaded reference image (max 1).
 *
 * Features:
 * - Same style as Selected Hero Image
 * - Delete button on hover
 * - Full width display
 */

'use client';

import { X, Maximize2 } from 'lucide-react';
import { useState } from 'react';
import { ImageExpandModal } from './ImageExpandModal';
import { API_BASE_URL } from '@/config';
import { cn } from '@/lib/utils';
import { useProjectStore } from '@/stores/useProjectStore';

interface ImageAsset {
  asset_id: string;
  url: string;
  description: string;
  generation_params?: any;
}

interface ReferenceImagesDisplayProps {
  images: ImageAsset[];
  projectId: string;
}

export function ReferenceImagesDisplay({ images, projectId }: ReferenceImagesDisplayProps) {
  const [deleting, setDeleting] = useState(false);
  const [expandedImage, setExpandedImage] = useState<{ url: string; description: string } | null>(null);
  const { updateBrief } = useProjectStore();

  const handleDelete = async (assetId: string) => {
    if (deleting) return;

    setDeleting(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/reference-images/${assetId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete image');
      }

      console.log(`[ReferenceImages] Deleted image ${assetId}`);

      // Fetch updated brief and update store
      const briefResponse = await fetch(`${API_BASE_URL}/api/projects/${projectId}`);
      if (briefResponse.ok) {
        const updatedBrief = await briefResponse.json();
        updateBrief(updatedBrief, ['reference_images']);
        console.log(`[ReferenceImages] Updated brief with ${updatedBrief.reference_images?.length || 0} reference images`);
      }
    } catch (error) {
      console.error('Error deleting reference image:', error);
      alert('Failed to delete image. Please try again.');
    } finally {
      setDeleting(false);
    }
  };

  if (images.length === 0) {
    return null;
  }

  // Show only the first image (max 1)
  const image = images[0];

  return (
    <>
      <div className="relative group">
        <img
          src={image.url}
          alt={image.description}
          className="w-full rounded border border-zinc-700"
        />

        {/* Hover overlay with expand and delete buttons */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded flex items-start justify-end p-2 gap-1">
          <button
            onClick={() => setExpandedImage({ url: image.url, description: image.description })}
            className="bg-zinc-700 hover:bg-zinc-600 p-1 rounded text-white transition-colors"
            title="View full size"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleDelete(image.asset_id)}
            disabled={deleting}
            className={cn(
              "bg-red-500 hover:bg-red-600 p-1 rounded text-white transition-colors",
              deleting && "opacity-50 cursor-not-allowed"
            )}
            title="Delete reference image"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Full-size Image Modal */}
      <ImageExpandModal
        image={expandedImage}
        onClose={() => setExpandedImage(null)}
      />
    </>
  );
}
