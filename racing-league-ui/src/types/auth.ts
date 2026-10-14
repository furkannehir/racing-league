export interface LoginRequest {
    email: string;
    password: string;
}

export interface AuthUser {
    id: string;
    mongoId: string;
    email: string;
    name: string;
    username?: string;
    profilePicture?: string;
}

export interface LoginResponse {
    token: string;
    refreshToken: string;
    expiresIn: number;
    user: AuthUser;
}

export interface RegistrationResponse {
    uid: string;
    message: string;
    emailStatus: 'queued';
}

export interface AccountEmailResponse {
    message: string;
    code: 'email_queued';
}
