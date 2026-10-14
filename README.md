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

Provide `racing-league-app/.env` and `racing-league-app/serviceAccountKey.json` locally.
Compose injects them at runtime; they are excluded from Docker images. Configure
the backend's `ORIGINS` to include `http://localhost:3000` and use a MongoDB replica
set as described in the [backend README](racing-league-app/README.md).

```bash
docker compose up --build -d
```

The local frontend build explicitly targets `http://localhost:5000/api`.
Production frontend builds require `VITE_API_URL` to be set to the intended
backend URL, including `/api`. See the [frontend configuration instructions](racing-league-ui/README.md#build-and-deployment-configuration).
Set the backend's `FRONTEND_URL` to your frontend's public origin for invitation
links. Compose defaults it to `http://localhost:3000`.
### Local Development
#### Backend
```bash
cd racing-league-app
pip install -r requirements.txt
python app.py
```
#### Frontend
```bash
cd racing-league-ui
npm install
npm run dev
```

For an existing database, follow the [backend migration instructions](racing-league-app/README.md#database-migration-before-deployment) before deploying the new schema.

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
