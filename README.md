# Racing League Management System

## Introduction
This is a comprehensive racing league management system built with a Flask backend API and React (Vite) frontend. The application allows league administrators to manage races, teams, drivers, and results, while providing participants and fans with real-time information about upcoming events and standings.
### Demo page
https://www.pushtopass.app/

## Tech Stack

### Backend
- Python 3.12
- Flask
- Firebase Authentication
- Docker

### Frontend
- React with Vite
- TypeScript
- Material UI

## Setup

### Prerequisites
- Docker and Docker Compose
- Node.js and npm (for local development)
- Python 3.12 (for local development)

### Using Docker
```bash
docker-compose up -d
```
### Local Development
#### Backend
```bash
cd racing-league-app
pip install -r requirements.txt
python src/app.py
```
#### Frontend
```bash
cd racing-league-ui
npm install
npm run dev
```

## Project Structure
```
├── racing-league-app
│   ├── src
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── auth_module
│   │   ├── league_module
│   │   ├── invite_module
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env
├── racing-league-ui
│   ├── src
│   │   ├── components
│   │   ├── pages
│   │   ├── App.tsx
│   │   ├── index.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── Dockerfile
│   ├── .env
├── docker-compose.yml
```

## API Endpoints

- Authentication routes
- League management routes
- Invitation system routes

## Features
- League Management: Create, join, and manage racing leagues
- Race Calendar: Schedule and track upcoming and completed races
- Results Management: Submit and view race results
- Standings: Track driver standings within leagues
- User Authentication: Secure login and registration
- Admin Controls: League settings, member management, and race administration
