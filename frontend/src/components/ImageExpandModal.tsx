/**
 * Image Expand Modal - Reusable modal for viewing full-size images.
 *
 * Features:
 * - Full-screen overlay with dark background
 * - Close on click outside or X button
 * - Displays image description
 */

'use client';

import { X } from 'lucide-react';

interface ImageExpandModalProps {
  image: { url: string; description: string } | null;
  onClose: () => void;
}

export function ImageExpandModal({ image, onClose }: ImageExpandModalProps) {
  if (!image) return null;

  return (
    <div
      className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <button
        onClick={onClose}
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
          src={image.url}
          alt={image.description}
          className="max-w-full max-h-[85vh] object-contain rounded-lg"
        />
        <div className="mt-3 text-center text-sm text-zinc-400">
          {image.description}
        </div>
      </div>
    </div>
  );
}
