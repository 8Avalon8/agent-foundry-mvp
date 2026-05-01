public class UserProfileService {
    public String displayName(User user) {
        return user.getName().trim();
    }
}
