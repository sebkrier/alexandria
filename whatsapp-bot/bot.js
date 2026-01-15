const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

// Configuration
const ALEXANDRIA_API = process.env.ALEXANDRIA_API || 'http://localhost:8000/api';

// URL regex pattern
const URL_REGEX = /https?:\/\/[^\s<>"{}|\\^`\[\]]+/gi;

// Create WhatsApp client with local authentication (persists session)
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: './.wwebjs_auth'
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// QR Code event - display in terminal for scanning
client.on('qr', (qr) => {
    console.log('\n========================================');
    console.log('  SCAN THIS QR CODE WITH WHATSAPP');
    console.log('========================================\n');
    qrcode.generate(qr, { small: true });
    console.log('\nOpen WhatsApp > Settings > Linked Devices > Link a Device\n');
});

// Ready event
client.on('ready', () => {
    console.log('\n========================================');
    console.log('  WHATSAPP BOT IS READY!');
    console.log('========================================');
    console.log('\nSend a URL in any chat to add articles to Alexandria.');
    console.log('Only YOUR messages are processed (not messages from others).');
    console.log('Tip: Send links to yourself or any chat - they\'ll be captured!\n');
});

// Authentication success
client.on('authenticated', () => {
    console.log('Authentication successful! Session saved.');
});

// Authentication failure
client.on('auth_failure', (msg) => {
    console.error('Authentication failed:', msg);
});

// Disconnected
client.on('disconnected', (reason) => {
    console.log('Client was disconnected:', reason);
});

// Helper to send message to a chat (may fail for self-chats due to whatsapp-web.js bug)
async function sendToChat(message, text) {
    try {
        const chat = await message.getChat();
        await client.sendMessage(chat.id._serialized, text);
    } catch (err) {
        // Silently fail - whatsapp-web.js has a bug with self-chat messages
        // The article was still added successfully, just can't send confirmation
        console.log(`(Could not send WhatsApp reply: ${err.message})`);
    }
}

// Message handler - using message_create to catch all messages including self-sent
client.on('message_create', async (message) => {
    // Only process messages sent BY you (not messages from others)
    if (!message.fromMe) {
        return;
    }

    const body = message.body.trim();

    console.log(`Processing self-sent message: ${body}`);

    // Handle commands
    const lowerBody = body.toLowerCase();

    if (lowerBody === 'status') {
        await sendToChat(message, 'Alexandria WhatsApp Bot is running and connected!');
        return;
    }

    if (lowerBody === 'help') {
        await sendToChat(message,
            '*Alexandria WhatsApp Bot*\n\n' +
            'Send any URL in any chat and it\'ll be added to your Alexandria library.\n' +
            'Only YOUR messages are captured (links from others are ignored).\n\n' +
            'Supported:\n' +
            '• Web articles\n' +
            '• YouTube videos\n' +
            '• arXiv papers\n' +
            '• PDF links\n\n' +
            'Commands:\n' +
            '• *status* - Check if bot is running\n' +
            '• *help* - Show this message'
        );
        return;
    }

    // Extract URLs from message
    const urls = body.match(URL_REGEX);

    if (!urls || urls.length === 0) {
        // Don't reply to random messages, only URL-related ones
        if (body.includes('http') || body.includes('www.')) {
            await sendToChat(message, "I couldn't detect a valid URL. Please send a complete link starting with http:// or https://");
        }
        return;
    }

    // Process each URL
    for (const url of urls) {
        try {
            console.log(`Adding article: ${url}`);

            const response = await axios.post(`${ALEXANDRIA_API}/articles`, {
                url: url
            }, {
                timeout: 30000,
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const article = response.data;
            const title = article.title || 'Untitled';
            const status = article.processing_status;

            let replyMsg = `Added to Alexandria!\n\n*${title}*\n\nStatus: ${status}`;

            if (status === 'pending' || status === 'processing') {
                replyMsg += '\n\n_AI summary will be generated shortly._';
            }

            await sendToChat(message, replyMsg);
            console.log(`Successfully added: ${title}`);

        } catch (error) {
            console.error('Error adding article:', error.message);

            let errorMsg = 'Failed to add article.';

            if (error.response) {
                const detail = error.response.data?.detail;
                if (detail) {
                    errorMsg += `\n\nError: ${detail}`;
                }
            } else if (error.code === 'ECONNREFUSED') {
                errorMsg = 'Cannot connect to Alexandria. Make sure the server is running.';
            } else if (error.code === 'ETIMEDOUT') {
                errorMsg = 'Request timed out. The article might still be processing.';
            }

            await sendToChat(message, errorMsg);
        }
    }
});

// Error handler
client.on('error', (error) => {
    console.error('Client error:', error);
});

// Start the client
console.log('Starting Alexandria WhatsApp Bot...');
console.log('Connecting to WhatsApp Web...\n');
client.initialize();

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\nShutting down...');
    await client.destroy();
    process.exit(0);
});
