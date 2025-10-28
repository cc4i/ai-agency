'use client'

import { useEffect, useState } from 'react'

export default function WorkspaceClient() {
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    setIsReady(true)
  }, [])

  if (!isReady) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold">AI Agency</h1>
          <p className="text-muted-foreground mt-2">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">Welcome, Creative Director.</h1>
          <button className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            Show Me the API
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Project Brief Panel (Left) */}
        <aside className="w-80 border-r border-border bg-card p-6">
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold mb-2">Project Brief</h2>
              <p className="text-sm text-muted-foreground">
                Campaign details will appear here as you work with the Executive Producer.
              </p>
            </div>
          </div>
        </aside>

        {/* Workspace (Center) */}
        <main className="flex-1 overflow-auto p-6">
          <div className="flex h-full items-center justify-center">
            <div className="text-center max-w-md">
              <div className="mb-8">
                <div className="w-24 h-24 mx-auto rounded-full bg-primary/20 flex items-center justify-center mb-4">
                  <svg
                    className="w-12 h-12 text-primary"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                    />
                  </svg>
                </div>
                <h2 className="text-2xl font-bold mb-2">Ready to Begin</h2>
                <p className="text-muted-foreground mb-6">
                  Click the microphone and say "Let&apos;s get started" to begin your campaign.
                </p>
              </div>

              {/* Placeholder for persistent microphone */}
              <div className="microphone-glow inline-block">
                <button className="w-20 h-20 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 transition-all">
                  <svg
                    className="w-10 h-10"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                    />
                  </svg>
                </button>
              </div>
              <p className="text-sm text-muted-foreground mt-4">Click to speak</p>
            </div>
          </div>
        </main>

        {/* Conversation Panel (Right) */}
        <aside className="w-96 border-l border-border bg-card p-6">
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold mb-2">Conversation</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Audio + Text Transcript
              </p>
            </div>

            <div className="space-y-3 text-sm">
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="flex items-start gap-2">
                  <span className="text-lg">🤖</span>
                  <div className="flex-1">
                    <p className="font-medium text-xs text-muted-foreground mb-1">Producer</p>
                    <p>Welcome. I&apos;m your Executive Producer. Ready to create something amazing?</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
