let i18nData = {};
let currentLang = localStorage.getItem('heater_lang') || 'en';
let currentTheme = localStorage.getItem('heater_theme') || 'light';
let currentChatId = null;
let windowChatMessages = {};
let currentAbortController = null;
let isGenerating = false;
let attachedRawFile = null;
let frontendImageBase64 = null;
let frontendTextContent = null;
let sessionFileCache = {};

let currentAudio = null;
let currentAudioMsgId = null;
let activeGenerations = {};

let uploadedImageWidth = 0;
let uploadedImageHeight = 0;
let attachedRawFiles = [];

let canvas, ctx, particles = [];

let currentCanvasTheme = 'particles';
let bezierLines = [];
let waveTime = 0;
let wakeLock = null;
let currentUITheme = localStorage.getItem('heater_ui_theme') || 'modern';

let ollamaModels = [];

let rssArchiveData = [];
let rssFilteredData = [];
let rssCurrentPage = 1;

const RSS_PAGE_SIZE = 50;

let kbFilesData = [];
let kbFilesFiltered = [];
let kbFilesPage = 1;

let kbUrlsData = [];
let kbUrlsFiltered = [];
let kbUrlsPage = 1;

const KB_PAGE_SIZE = 50;

const accentColors = {
    azure: { main: '#0ea5e9', hover: '#0284c7', light: 'rgba(14, 165, 233, 0.15)' },
    gold: { main: '#fbbf24', hover: '#d97706', light: 'rgba(251, 191, 36, 0.15)' },
    turquoise: { main: '#2dd4bf', hover: '#0f766e', light: 'rgba(45, 212, 191, 0.15)' },
    purple: { main: '#a855f7', hover: '#7e22ce', light: 'rgba(168, 85, 247, 0.15)' },
    red: { main: '#f87171', hover: '#dc2626', light: 'rgba(248, 113, 113, 0.15)' },
    green: { main: '#4ade80', hover: '#16a34a', light: 'rgba(74, 222, 128, 0.15)' }
};

let currentAccentColor = localStorage.getItem('heater_accent_color') || 'azure';
