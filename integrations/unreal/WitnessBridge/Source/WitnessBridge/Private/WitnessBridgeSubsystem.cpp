#include "WitnessBridgeSubsystem.h"

#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HighResScreenshot.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

void UWitnessBridgeSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    BridgeDirectory = FPlatformMisc::GetEnvironmentVariable(TEXT("WITNESS_BRIDGE_DIR"));
    if (BridgeDirectory.IsEmpty()) return;
    BridgeDirectory = FPaths::ConvertRelativePathToFull(BridgeDirectory);
    IFileManager::Get().MakeDirectory(*BridgeDirectory, true);
    CommandPath = FPaths::Combine(BridgeDirectory, TEXT("command.json"));
    AckPath = FPaths::Combine(BridgeDirectory, TEXT("ack.json"));
    bEnabled = true;
}

void UWitnessBridgeSubsystem::Tick(float DeltaTime)
{
    const double Now = FPlatformTime::Seconds();
    if (!bEnabled || Now < NextPollSeconds || !FPaths::FileExists(CommandPath)) return;
    NextPollSeconds = Now + 0.05;
    const FDateTime WriteTime = IFileManager::Get().GetTimeStamp(*CommandPath);
    if (WriteTime <= LastWriteTime) return;
    LastWriteTime = WriteTime;

    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *CommandPath)) return;
    TSharedPtr<FJsonObject> Command;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, Command) || !Command.IsValid()) return;

    const FString Id = Command->GetStringField(TEXT("id"));
    const FString Kind = Command->GetStringField(TEXT("kind"));
    if (Kind == TEXT("capture"))
    {
        const FString Output = FPaths::ConvertRelativePathToFull(Command->GetStringField(TEXT("output")));
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(Output), true);
        FScreenshotRequest::RequestScreenshot(Output, false, false);
        WriteAck(Id, true, TEXT(""));
        return;
    }
    if (Kind == TEXT("click") || Kind == TEXT("press"))
    {
        FString Target, Key;
        Command->TryGetStringField(TEXT("target"), Target);
        Command->TryGetStringField(TEXT("key"), Key);
        double X = 0.0, Y = 0.0;
        Command->TryGetNumberField(TEXT("x"), X);
        Command->TryGetNumberField(TEXT("y"), Y);
        OnNamedAction.Broadcast(Target, Key, static_cast<int32>(X), static_cast<int32>(Y));
        WriteAck(Id, true, TEXT(""));
        return;
    }
    WriteAck(Id, false, FString::Printf(TEXT("Unsupported action kind: %s"), *Kind));
}

void UWitnessBridgeSubsystem::WriteAck(const FString& Id, bool bOk, const FString& Error) const
{
    TSharedRef<FJsonObject> Ack = MakeShared<FJsonObject>();
    Ack->SetStringField(TEXT("id"), Id);
    Ack->SetBoolField(TEXT("ok"), bOk);
    Ack->SetStringField(TEXT("error"), Error);
    FString JsonText;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonText);
    FJsonSerializer::Serialize(Ack, Writer);
    const FString Temporary = AckPath + TEXT(".tmp");
    FFileHelper::SaveStringToFile(JsonText, *Temporary);
    IFileManager::Get().Move(*AckPath, *Temporary, true, true, false, true);
}
