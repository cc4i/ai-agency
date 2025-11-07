/**
 * Project Brief Panel - Real-time updating sidebar.
 *
 * Features:
 * - Displays project brief with all details
 * - Highlights recently changed fields with animation
 * - Shows selected slogan and image
 * - Persistent throughout workflow
 */

'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/stores/useProjectStore';
import { cn } from '@/lib/utils';
import { ReferenceImageUpload } from './ReferenceImageUpload';
import { ReferenceImagesDisplay } from './ReferenceImagesDisplay';

export function ProjectBriefPanel() {
  const { brief, changedFields, clearChangedFields } = useProjectStore();
  const [highlightedFields, setHighlightedFields] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (changedFields.length > 0) {
      setHighlightedFields(new Set(changedFields));

      // Clear highlights after 2 seconds
      const timeout = setTimeout(() => {
        setHighlightedFields(new Set());
        clearChangedFields();
      }, 2000);

      return () => clearTimeout(timeout);
    }
  }, [changedFields, clearChangedFields]);

  if (!brief) {
    return (
      <div className="w-80 border-r border-zinc-800 bg-zinc-950 p-6">
        <div className="text-zinc-500">No Project loaded</div>
      </div>
    );
  }

  const isFieldHighlighted = (field: string) => highlightedFields.has(field);

  return (
    <div className="w-80 border-r border-zinc-800 bg-zinc-950 flex flex-col h-full">
      <div className="p-3 flex-shrink-0">
        <h2 className="text-sm font-semibold text-white mb-2">Project Brief</h2>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3">
        <div className="space-y-1.5">
        {/* Product with Upload Icon */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex-1">
            <BriefField
              label="Product"
              value={brief.product_name}
              highlighted={isFieldHighlighted('product_name')}
            />
          </div>
          <ReferenceImageUpload projectId={brief.project_id} />
        </div>

        {/* Reference Images - Right below product */}
        {brief.reference_images && brief.reference_images.length > 0 && (
          <div
            className={cn(
              'transition-colors duration-500',
              isFieldHighlighted('reference_images') && 'bg-purple-500/10 -mx-2 px-2 py-1 rounded'
            )}
          >
            <div className="text-xs font-medium text-zinc-400 mb-2">Reference Images</div>
            <ReferenceImagesDisplay images={brief.reference_images} projectId={brief.project_id} />
          </div>
        )}

        <BriefField
          label="Category"
          value={brief.product_category}
          highlighted={isFieldHighlighted('product_category')}
        />

        <BriefField
          label="Theme"
          value={brief.theme}
          highlighted={isFieldHighlighted('theme')}
        />

        <BriefField
          label="Brand Tone"
          value={brief.brand_tone}
          highlighted={isFieldHighlighted('brand_tone')}
        />

        <BriefField
          label="Target Market"
          value={brief.target_market}
          highlighted={isFieldHighlighted('target_market')}
        />

        {brief.key_features && brief.key_features.length > 0 && (
          <div
            className={cn(
              'transition-colors duration-500',
              isFieldHighlighted('key_features') && 'bg-blue-500/10 -mx-2 px-2 py-1 rounded'
            )}
          >
            <div className="text-xs font-medium text-zinc-400 mb-1">Key Features</div>
            <ul className="list-disc list-inside text-sm text-zinc-300 space-y-0.5">
              {brief.key_features.map((feature, i) => (
                <li key={i}>{feature}</li>
              ))}
            </ul>
          </div>
        )}

        {brief.selected_slogan && (
          <div
            className={cn(
              'transition-colors duration-500',
              isFieldHighlighted('selected_slogan') && 'bg-green-500/10 -mx-2 px-2 py-1 rounded'
            )}
          >
            <div className="text-xs font-medium text-zinc-400 mb-1">Selected Slogan</div>
            <div className="text-sm font-medium text-green-400">{brief.selected_slogan}</div>
          </div>
        )}

        {brief.selected_image && (
          <div
            className={cn(
              'transition-colors duration-500',
              isFieldHighlighted('selected_image') && 'bg-purple-500/10 -mx-2 px-2 py-1 rounded'
            )}
          >
            <div className="text-xs font-medium text-zinc-400 mb-2">Selected Hero Image</div>
            <img
              src={brief.selected_image.url}
              alt="Selected hero"
              className="w-full rounded border border-zinc-700"
            />
          </div>
        )}

        {/* Only show initial sketch if no hero image has been selected */}
        {!brief.selected_image && brief.initial_sketch_url && (
          <div>
            <div className="text-xs font-medium text-zinc-400 mb-2">Initial Sketch</div>
            <img
              src={brief.initial_sketch_url}
              alt="Initial sketch"
              className="w-full rounded border border-zinc-700"
            />
          </div>
        )}
      </div>

        <div className="mt-3 pt-3 border-t border-zinc-800 text-xs text-zinc-500">
          <div>Updated: {new Date(brief.updated_at).toLocaleTimeString()}</div>
        </div>
      </div>
    </div>
  );
}

interface BriefFieldProps {
  label: string;
  value: string;
  highlighted?: boolean;
}

function BriefField({ label, value, highlighted }: BriefFieldProps) {
  return (
    <div
      className={cn(
        'transition-colors duration-500',
        highlighted && 'bg-blue-500/10 -mx-2 px-2 py-1 rounded'
      )}
    >
      <div className="text-xs font-medium text-zinc-400 mb-0.5">{label}</div>
      <div className="text-sm text-zinc-200">{value}</div>
    </div>
  );
}
