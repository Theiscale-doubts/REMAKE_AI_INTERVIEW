# VoxHire - Tech Mock Interviewer App

A modern, voice-first tech interview application built with React, Tailwind CSS, and TypeScript. This app allows candidates to record voice answers to technical interview questions with instant playback and export functionality.

## Features

- **Voice-First Interface**: Record audio answers directly in the browser
- **Multiple Roles**: Frontend Developer, Data Scientist, Product Manager, DevOps Engineer
- **Role-Specific Questions**: Tailored question banks for each role
- **Audio Recording & Playback**: Built-in audio recording with instant playback
- **Progress Tracking**: Visual progress bar and question counter
- **Results Review**: Review all recorded answers with durations
- **Export Functionality**: Export interview data as JSON
- **Local Storage**: All audio data stays in the browser (no server upload)
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Dark Theme**: Modern dark interface with smooth animations

## Project Structure

```
voxhire-app/
├── client/
│   ├── public/              # Static assets
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Page components (Home, Interview, Results)
│   │   ├── contexts/        # React contexts (Theme)
│   │   ├── hooks/           # Custom React hooks
│   │   ├── lib/             # Utility functions
│   │   ├── App.tsx          # Main app routing
│   │   ├── main.tsx         # React entry point
│   │   └── index.css        # Global styles
│   └── index.html           # HTML template
├── package.json             # Project dependencies
├── pnpm-lock.yaml          # Dependency lock file
├── tsconfig.json           # TypeScript configuration
├── vite.config.ts          # Vite build configuration
└── tailwind.config.ts      # Tailwind CSS configuration
```

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** (v18 or higher)
- **pnpm** (v8 or higher) - Package manager

## Installation & Setup

### 1. Extract the Project

```bash
unzip voxhire-app.zip
cd voxhire-app
```

### 2. Install Dependencies

```bash
pnpm install
```

This will install all required packages including React, Tailwind CSS, and other dependencies.

### 3. Start the Development Server

```bash
pnpm dev
```

The application will start on `http://localhost:3000` (or another available port).

### 4. Open in Browser

Open your web browser and navigate to `http://localhost:3000` to access the application.

## Usage

### Home Page

The landing page showcases the app's features with:
- Hero section with call-to-action buttons
- Feature cards highlighting key capabilities
- How-it-works section with three steps
- Testimonial section
- Navigation to interview and results pages

### Interview Page

1. **Select a Role**: Choose from Frontend Developer, Data Scientist, Product Manager, or DevOps Engineer
2. **Read Questions**: Each role has 3 tailored technical questions
3. **Record Answers**: Click "Start recording" to begin recording your voice answer
4. **Review & Retake**: Listen to your recording and retake if needed
5. **Submit Answer**: Submit your answer to move to the next question
6. **Complete Interview**: After all questions, view the completion message

### Results Page

- View a summary of your interview (role, date, duration, question count)
- Review each recorded answer with playback
- Export interview data as JSON
- Clear data to start fresh

## Browser Compatibility

The app works best on modern browsers that support:
- Web Audio API
- MediaRecorder API
- HTML5 Audio Element

**Recommended Browsers:**
- Chrome/Chromium (v60+)
- Firefox (v55+)
- Edge (v79+)
- Safari (v14+)

## Building for Production

To create an optimized production build:

```bash
pnpm build
```

The build output will be in the `dist/` directory, ready for deployment.

## Technology Stack

- **React 19**: UI framework
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS 4**: Utility-first CSS framework
- **shadcn/ui**: High-quality React components
- **Lucide React**: Icon library
- **Wouter**: Lightweight routing library
- **Vite**: Fast build tool and dev server

## Key Features Explained

### Audio Recording

The app uses the Web Audio API and MediaRecorder to capture audio directly in the browser:
- Automatic format detection (WebM, Ogg, MP4)
- Real-time visualizer during recording
- Auto-stop after 120 seconds
- Manual stop button for shorter answers

### Local Storage

All audio data is stored locally in the browser using Blob objects:
- No data is sent to any server
- Data persists during the session
- Users can export data as JSON
- Clear button to reset all data

### Responsive Design

The interface adapts to different screen sizes:
- Mobile: Single column layout with stacked components
- Tablet: Two-column layout with adjusted spacing
- Desktop: Full three-column layout with optimal spacing

## Troubleshooting

### Microphone Permission Denied

If you see "Microphone permission denied" error:
1. Check your browser's microphone permissions
2. Allow microphone access when prompted
3. Refresh the page and try again

### Audio Not Recording

If audio doesn't record:
1. Ensure your browser supports MediaRecorder API
2. Check that your microphone is working
3. Try a different browser
4. Clear browser cache and try again

### Build Errors

If you encounter build errors:
1. Delete `node_modules` folder: `rm -rf node_modules`
2. Clear pnpm cache: `pnpm store prune`
3. Reinstall dependencies: `pnpm install`
4. Restart dev server: `pnpm dev`

## Development Commands

```bash
# Start development server
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview

# Run type checking
pnpm typecheck

# Format code
pnpm format

# Lint code
pnpm lint
```

## Future Enhancements

Potential features to add:
- Server-side storage for interview results
- User authentication and profiles
- Interview analytics and scoring
- Video recording alongside audio
- Real-time transcription
- Interview templates and customization
- Team collaboration features
- Mobile app version

## License

This project is provided as-is for educational and commercial use.

## Support

For issues, questions, or feature requests, please refer to the project documentation or contact the development team.

---

**Version**: 1.0.0  
**Last Updated**: November 2024
