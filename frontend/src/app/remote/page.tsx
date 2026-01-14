"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { AddArticleModal } from "@/components/articles/AddArticleModal";
import { MessageSquare, Smartphone, Monitor, Terminal, CheckCircle, Copy, Check } from "lucide-react";
import { useState } from "react";

export default function RemotePage() {
  const [copiedStep, setCopiedStep] = useState<number | null>(null);

  const copyToClipboard = (text: string, step: number) => {
    navigator.clipboard.writeText(text);
    setCopiedStep(step);
    setTimeout(() => setCopiedStep(null), 2000);
  };

  return (
    <div className="min-h-screen bg-dark-bg flex">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <Header />

        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center">
                <MessageSquare className="w-6 h-6 text-green-500" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">Remote Add via WhatsApp</h1>
                <p className="text-dark-muted">Add articles to Alexandria from anywhere</p>
              </div>
            </div>

            {/* How it works */}
            <section className="bg-dark-surface border border-dark-border rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-4">How It Works</h2>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-dark-bg rounded-lg p-4 text-center">
                  <Smartphone className="w-8 h-8 text-article-blue mx-auto mb-2" />
                  <h3 className="font-medium text-white mb-1">From Anywhere</h3>
                  <p className="text-sm text-dark-muted">Phone, tablet, or any computer with WhatsApp</p>
                </div>
                <div className="bg-dark-bg rounded-lg p-4 text-center">
                  <MessageSquare className="w-8 h-8 text-green-500 mx-auto mb-2" />
                  <h3 className="font-medium text-white mb-1">Send a Link</h3>
                  <p className="text-sm text-dark-muted">Just paste any URL into the WhatsApp chat</p>
                </div>
                <div className="bg-dark-bg rounded-lg p-4 text-center">
                  <CheckCircle className="w-8 h-8 text-purple-500 mx-auto mb-2" />
                  <h3 className="font-medium text-white mb-1">Auto-Added</h3>
                  <p className="text-sm text-dark-muted">Article appears in your library with AI summary</p>
                </div>
              </div>

              <div className="bg-dark-bg rounded-lg p-4 border border-dark-border">
                <p className="text-sm text-dark-muted">
                  <strong className="text-white">Supported content:</strong> Web articles, YouTube videos, arXiv papers, PDF links
                </p>
              </div>
            </section>

            {/* Setup Instructions */}
            <section className="bg-dark-surface border border-dark-border rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-4">Setup Instructions</h2>

              <div className="space-y-4">
                {/* Step 1 */}
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 bg-article-blue rounded-full flex items-center justify-center text-white font-bold text-sm">
                    1
                  </div>
                  <div className="flex-1">
                    <h3 className="font-medium text-white mb-2">Install Dependencies</h3>
                    <p className="text-sm text-dark-muted mb-2">
                      Navigate to the WhatsApp bot folder and install packages:
                    </p>
                    <div className="bg-dark-bg rounded-lg p-3 font-mono text-sm flex items-center justify-between group">
                      <code className="text-green-400">cd whatsapp-bot && npm install</code>
                      <button
                        onClick={() => copyToClipboard("cd whatsapp-bot && npm install", 1)}
                        className="p-1 text-dark-muted hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        {copiedStep === 1 ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Step 2 */}
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 bg-article-blue rounded-full flex items-center justify-center text-white font-bold text-sm">
                    2
                  </div>
                  <div className="flex-1">
                    <h3 className="font-medium text-white mb-2">Start the Bot</h3>
                    <p className="text-sm text-dark-muted mb-2">
                      Run the bot - a QR code will appear in the terminal:
                    </p>
                    <div className="bg-dark-bg rounded-lg p-3 font-mono text-sm flex items-center justify-between group">
                      <code className="text-green-400">npm start</code>
                      <button
                        onClick={() => copyToClipboard("npm start", 2)}
                        className="p-1 text-dark-muted hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        {copiedStep === 2 ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 bg-article-blue rounded-full flex items-center justify-center text-white font-bold text-sm">
                    3
                  </div>
                  <div className="flex-1">
                    <h3 className="font-medium text-white mb-2">Scan QR Code</h3>
                    <p className="text-sm text-dark-muted mb-2">
                      On your phone, open WhatsApp and scan the QR code:
                    </p>
                    <div className="bg-dark-bg rounded-lg p-4 text-sm text-dark-muted">
                      <ol className="list-decimal list-inside space-y-1">
                        <li>Open WhatsApp on your phone</li>
                        <li>Go to <strong className="text-white">Settings → Linked Devices</strong></li>
                        <li>Tap <strong className="text-white">Link a Device</strong></li>
                        <li>Scan the QR code shown in the terminal</li>
                      </ol>
                    </div>
                  </div>
                </div>

                {/* Step 4 */}
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                    ✓
                  </div>
                  <div className="flex-1">
                    <h3 className="font-medium text-white mb-2">Ready to Use!</h3>
                    <p className="text-sm text-dark-muted">
                      Send any URL to yourself on WhatsApp (message your own number or save it as a contact).
                      The bot will add it to Alexandria and confirm.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {/* Usage Tips */}
            <section className="bg-dark-surface border border-dark-border rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-4">Usage Tips</h2>

              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <Terminal className="w-5 h-5 text-article-blue mt-0.5" />
                  <div>
                    <h3 className="font-medium text-white">Keep the bot running</h3>
                    <p className="text-sm text-dark-muted">
                      The bot needs to stay running on your Alexandria machine. Consider using a process manager like PM2
                      or running it as a system service.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <Monitor className="w-5 h-5 text-purple-500 mt-0.5" />
                  <div>
                    <h3 className="font-medium text-white">Session persists</h3>
                    <p className="text-sm text-dark-muted">
                      You only need to scan the QR code once. The session is saved and will reconnect automatically.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <MessageSquare className="w-5 h-5 text-green-500 mt-0.5" />
                  <div>
                    <h3 className="font-medium text-white">Bot commands</h3>
                    <p className="text-sm text-dark-muted">
                      Send <code className="bg-dark-bg px-1.5 py-0.5 rounded text-xs">help</code> to see instructions
                      or <code className="bg-dark-bg px-1.5 py-0.5 rounded text-xs">status</code> to check if the bot is running.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {/* Run with PM2 */}
            <section className="bg-dark-surface border border-dark-border rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Keep Bot Running (Optional)</h2>
              <p className="text-sm text-dark-muted mb-4">
                Use PM2 to keep the bot running in the background and auto-restart on boot:
              </p>

              <div className="space-y-2">
                <div className="bg-dark-bg rounded-lg p-3 font-mono text-sm flex items-center justify-between group">
                  <code className="text-green-400">npm install -g pm2</code>
                  <button
                    onClick={() => copyToClipboard("npm install -g pm2", 5)}
                    className="p-1 text-dark-muted hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {copiedStep === 5 ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
                <div className="bg-dark-bg rounded-lg p-3 font-mono text-sm flex items-center justify-between group">
                  <code className="text-green-400">pm2 start bot.js --name alexandria-whatsapp</code>
                  <button
                    onClick={() => copyToClipboard("pm2 start bot.js --name alexandria-whatsapp", 6)}
                    className="p-1 text-dark-muted hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {copiedStep === 6 ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
                <div className="bg-dark-bg rounded-lg p-3 font-mono text-sm flex items-center justify-between group">
                  <code className="text-green-400">pm2 startup && pm2 save</code>
                  <button
                    onClick={() => copyToClipboard("pm2 startup && pm2 save", 7)}
                    className="p-1 text-dark-muted hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {copiedStep === 7 ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </section>
          </div>
        </main>
      </div>

      <AddArticleModal />
    </div>
  );
}
