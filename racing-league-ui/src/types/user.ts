export interface UserProfile {
    id: string;
    username: string;
    email: string;
    firstName: string;
    lastName: string;
    bio?: string;
    preferences?: Record<string, any>;
    createdAt: string;
}