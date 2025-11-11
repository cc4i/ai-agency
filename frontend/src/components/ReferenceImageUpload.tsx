/**
 * Reference Image Upload - Upload button for adding reference image.
 *
 * Features:
 * - File picker for PNG/JPG images
 * - Single file upload (max 1)
 * - Client-side validation (type, size)
 * - Upload to backend and add to project brief
 */

'use client';

import { Upload } from 'lucide-react';
import { useRef, useState, ChangeEvent } from 'react';
import { cn } from '@/lib/utils';
import { useProjectStore } from '@/stores/useProjectStore';

interface ReferenceImageUploadProps {
  projectId: string;
}

export function ReferenceImageUpload({ projectId }: ReferenceImageUploadProps) {
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { brief, updateBrief } = useProjectStore();

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    // Check if there's already a reference image
    if (brief?.reference_images && brief.reference_images.length > 0) {
      alert('Only 1 reference image allowed. Please delete the existing one first.');
      return;
    }

    // Validate max 1 file
    if (files.length > 1) {
      alert('Only 1 reference image allowed at a time');
      return;
    }

    setUploading(true);

    try {
      for (const file of files) {
        // Validate file type
        if (!['image/png', 'image/jpeg', 'image/jpg'].includes(file.type)) {
          alert(`${file.name}: Only PNG/JPG images allowed`);
          continue;
        }

        // Validate file size (5MB)
        if (file.size > 5 * 1024 * 1024) {
          alert(`${file.name}: File too large (max 5MB)`);
          continue;
        }

        console.log(`[ReferenceUpload] Uploading ${file.name}...`);

        // Upload file
        const formData = new FormData();
        formData.append('file', file);

        const uploadResponse = await fetch('http://localhost:8000/api/assets/upload', {
          method: 'POST',
          body: formData,
        });

        if (!uploadResponse.ok) {
          const error = await uploadResponse.json();
          throw new Error(error.detail || 'Upload failed');
        }

        const imageAsset = await uploadResponse.json();
        console.log(`[ReferenceUpload] Uploaded ${file.name}, asset_id: ${imageAsset.asset_id}`);

        // Add to project brief
        const addResponse = await fetch(`http://localhost:8000/api/projects/${projectId}/reference-images`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(imageAsset),
        });

        if (!addResponse.ok) {
          const error = await addResponse.json();
          throw new Error(error.detail || 'Failed to add image to project');
        }

        console.log(`[ReferenceUpload] Added ${file.name} to project ${projectId}`);
      }

      // Fetch updated brief and update store
      const briefResponse = await fetch(`http://localhost:8000/api/projects/${projectId}`);
      if (briefResponse.ok) {
        const updatedBrief = await briefResponse.json();
        updateBrief(updatedBrief, ['reference_images']);
        console.log(`[ReferenceUpload] Updated brief with ${updatedBrief.reference_images?.length || 0} reference images`);
      }
    } catch (error) {
      console.error('Error uploading reference images:', error);
      alert(`Failed to upload images: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <>
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading || (brief?.reference_images && brief.reference_images.length > 0)}
        className={cn(
          "group p-1.5 rounded-lg bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/30",
          "hover:from-purple-500/20 hover:to-blue-500/20 hover:border-purple-500/50",
          "transition-all duration-200 shadow-lg shadow-purple-500/10",
          (uploading || (brief?.reference_images && brief.reference_images.length > 0)) &&
            "opacity-40 cursor-not-allowed hover:from-purple-500/10 hover:to-blue-500/10"
        )}
        title={
          brief?.reference_images && brief.reference_images.length > 0
            ? "Delete existing reference image first"
            : "Upload reference image (max 1, PNG/JPG, 5MB)"
        }
      >
        <Upload className={cn(
          "w-4 h-4 text-purple-400 transition-colors",
          uploading && "animate-pulse",
          !uploading && !(brief?.reference_images && brief.reference_images.length > 0) && "group-hover:text-purple-300"
        )} />
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/jpg"
        onChange={handleFileSelect}
        className="hidden"
      />
    </>
  );
}
