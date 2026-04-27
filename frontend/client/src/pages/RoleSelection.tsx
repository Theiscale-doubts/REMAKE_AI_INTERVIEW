import { useState } from "react";
import { useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { ChevronDown, Shield } from "lucide-react";

export default function RoleSelection() {
  const [role, setRole] = useState("frontend");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [, navigate] = useLocation();

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setPhoto(event.target?.result as string);
      };
      reader.readAsDataURL(e.target.files[0]);
    }
  };

  const startInterview = () => {
    if (name && email && role) {
      navigate("/interview", {
        state: { role, name, email, photo },
      });
    } else {
      alert("Please fill in all fields.");
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      {/* Header */}
      <header className="sticky top-0 z-20 backdrop-blur supports-[backdrop-filter]:bg-neutral-950/60 bg-neutral-950/80 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 grid place-items-center rounded-md bg-white text-neutral-900 font-semibold tracking-tight">
              VH
            </div>
            <div className="flex flex-col">
              <span className="text-lg tracking-tight font-semibold">
                VoxHire
              </span>
              <span className="text-xs text-neutral-400">
                Voice-first interview
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-2xl mx-auto px-6 py-8">
        <section className="rounded-xl border border-white/10 bg-white/5">
          <div className="p-5 border-b border-white/10">
            <h2 className="text-2xl tracking-tight font-semibold">
              Get Started
            </h2>
            <p className="text-sm text-neutral-400 mt-1">
              Fill in your details and choose a role to begin.
            </p>
          </div>
          <div className="p-5 space-y-4">
            <div className="flex items-center gap-4">
              <div className="w-24 h-24 rounded-full bg-neutral-800 flex items-center justify-center">
                {photo ? (
                  <img
                    src={photo}
                    alt="user"
                    className="w-full h-full object-cover rounded-full"
                  />
                ) : (
                  <span className="text-xs text-neutral-400">Photo</span>
                )}
              </div>
              <div className="flex-1">
                <label className="block text-sm text-neutral-300 mb-1">
                  Upload Photo
                </label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoUpload}
                  className="w-full text-sm text-neutral-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-white/5 file:text-white hover:file:bg-white/10"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-neutral-300 mb-1">
                Full Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-neutral-900/60 border border-white/10 rounded-lg text-sm px-3 py-2.5 outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div>
              <label className="block text-sm text-neutral-300 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-neutral-900/60 border border-white/10 rounded-lg text-sm px-3 py-2.5 outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div>
              <label className="block text-sm text-neutral-300 mb-1">
                Job role
              </label>
              <div className="relative">
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full appearance-none bg-neutral-900/60 border border-white/10 rounded-lg text-sm px-3 py-2.5 pr-10 outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20"
                >
                  <option value="frontend">Front-End Developer</option>
                  <option value="datascience">Data Scientist</option>
                  <option value="product">Product Manager</option>
                  <option value="devops">DevOps Engineer</option>
                </select>
                <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400">
                  <ChevronDown className="h-4 w-4" />
                </div>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-white/5">
              <Shield className="h-4 w-4 text-neutral-400" />
              <p className="text-xs text-neutral-400">
                Your data is safe. Everything is processed locally.
              </p>
            </div>

            <Button
              onClick={startInterview}
              className="w-full mt-2"
            >
              Start Interview
            </Button>
          </div>
        </section>
      </main>
    </div>
  );
}