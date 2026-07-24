import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Restricted product: only the sign-in screen is public. Everything else
// requires a session; unauthenticated visitors get a real 302 to sign-in
// (mirrors the reference project — avoids auth.protect()'s 404).
const isPublicRoute = createRouteMatcher(["/sign-in(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    const { userId, redirectToSignIn } = await auth();
    if (!userId) {
      return redirectToSignIn({ returnBackUrl: req.url });
    }
  }
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
