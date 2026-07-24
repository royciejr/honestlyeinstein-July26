import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="flex justify-center pt-10">
      <SignIn />
    </div>
  );
}
