import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

// User identity is GitHub's stable numeric account ID, never email or username.
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [GitHub],
  session: { strategy: "jwt" },
  callbacks: {
    jwt({ token, account }) {
      if (account?.provider === "github" && /^\d{1,30}$/.test(account.providerAccountId)) {
        token.qeSubject = "github:" + account.providerAccountId;
      }
      return token;
    },
    session({ session, token }) {
      return { ...session, user: { ...session.user, id:
        typeof token.qeSubject === "string" ? token.qeSubject : "" } };
    },
  },
});
